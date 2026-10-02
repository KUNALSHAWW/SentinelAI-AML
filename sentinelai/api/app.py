"""
SentinelAI FastAPI application
==============================

Middleware order (outermost first): request context/metrics -> rate limit -> CORS -> gzip.
The single-page frontend is mounted last so API routes always win.
"""

from __future__ import annotations

import os
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.base import BaseHTTPMiddleware

from sentinelai.api.routes import router
from sentinelai.core import metrics
from sentinelai.core.config import settings
from sentinelai.core.logging import get_logger, request_id_var, setup_logging
from sentinelai.core.security import check_rate_limit
from sentinelai.db.session import dispose_engine, init_db
from sentinelai.models.schemas import ErrorResponse

logger = get_logger(__name__)

def resolve_frontend_dir() -> Path:
    """SENTINEL_FRONTEND_DIR, else ./frontend (Docker WORKDIR / repo root), else the source-tree copy."""
    explicit = os.environ.get("SENTINEL_FRONTEND_DIR")
    candidates = [Path(explicit)] if explicit else []
    candidates += [Path.cwd() / "frontend", Path(__file__).resolve().parent.parent.parent / "frontend"]
    return next((c for c in candidates if (c / "index.html").is_file()), candidates[-1])


FRONTEND_DIR = resolve_frontend_dir()
RATE_LIMIT_EXEMPT = ("/health", "/metrics")


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Assigns a request id (log correlation), logs, and records HTTP metrics."""

    async def dispatch(self, request: Request, call_next):
        supplied = request.headers.get("X-Request-ID", "")
        request_id = supplied if 0 < len(supplied) <= 64 and supplied.replace("-", "").isalnum() else uuid.uuid4().hex
        token = request_id_var.set(request_id)
        request.state.request_id = request_id
        start = time.perf_counter()
        try:
            response = await call_next(request)
        finally:
            request_id_var.reset(token)
        duration = time.perf_counter() - start
        route = getattr(request.scope.get("route"), "path", "unmatched")
        metrics.HTTP_REQUESTS.labels(request.method, route, str(response.status_code)).inc()
        metrics.HTTP_LATENCY.labels(route).observe(duration)
        logger.info("request", extra={"method": request.method, "path": request.url.path,
                                      "status": response.status_code, "duration_ms": round(duration * 1000, 1),
                                      "request_id": request_id})
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Process-Time-ms"] = str(round(duration * 1000, 1))
        for k, v in getattr(request.state, "rate_headers", {}).items():
            response.headers[k] = v
        return response


class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.url.path in RATE_LIMIT_EXEMPT or not request.url.path.startswith("/api"):
            return await call_next(request)
        blocked = await check_rate_limit(request)
        if blocked:
            return JSONResponse(status_code=429, headers=blocked, content=ErrorResponse(
                error_code="RATE_LIMIT_EXCEEDED", message="Too many requests - slow down",
                request_id=getattr(request.state, "request_id", None)).model_dump(mode="json"))
        return await call_next(request)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator:
    setup_logging(settings.monitoring.log_level, settings.monitoring.log_format, settings.monitoring.log_file)
    if settings.database.auto_create_tables:
        await init_db()
    from sentinelai.engine.sanctions import get_screener
    info = get_screener().info
    logger.info("SentinelAI ready", extra={
        "environment": settings.environment, "regime": settings.risk.regime, "llm_configured": settings.llm.api_key_configured,
        "web_search": settings.llm.web_search_enabled, "sanctions_source": info["source"], "sanctions_entries": info["entries"]})
    if settings.is_production and not settings.api.api_keys and not settings.api.public_demo:
        logger.warning("Production without SENTINEL_API_KEYS: protected endpoints will reject all requests")
    yield
    await dispose_engine()


def create_app() -> FastAPI:
    app = FastAPI(
        title="SentinelAI",
        description=(
            "Explainable AML detection: a deterministic engine (sanctions & PEP screening, jurisdiction risk, "
            "behavioural typologies, transaction-graph motifs, crypto and trade checks) fused with a noisy-OR "
            "score, plus guarded LLM research that can raise but never lower a score. Persistent cases, "
            "SAR/STR drafts and a hash-chained audit trail. Auth: `X-API-Key` (roles viewer/analyst/admin)."),
        version=settings.app_version, docs_url="/docs", redoc_url="/redoc", openapi_url="/openapi.json", lifespan=lifespan)

    origins = settings.api.cors_origins
    wildcard = "*" in origins
    app.add_middleware(GZipMiddleware, minimum_size=1000)
    app.add_middleware(CORSMiddleware, allow_origins=origins, allow_credentials=not wildcard,
                       allow_methods=["*"], allow_headers=["*"], expose_headers=["X-Request-ID", "X-RateLimit-Remaining"])
    app.add_middleware(RateLimitMiddleware)
    app.add_middleware(RequestContextMiddleware)

    app.include_router(router)

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException):
        return JSONResponse(status_code=exc.status_code, headers=getattr(exc, "headers", None), content=ErrorResponse(
            error_code=f"HTTP_{exc.status_code}", message=str(exc.detail),
            request_id=getattr(request.state, "request_id", None)).model_dump(mode="json"))

    @app.exception_handler(Exception)
    async def unhandled(request: Request, exc: Exception):
        error_id = uuid.uuid4().hex[:12]
        logger.error("Unhandled exception (error_id=%s) on %s", error_id, request.url.path, exc_info=True)
        message = f"{type(exc).__name__}: {exc}" if settings.api.debug else "An internal error occurred"
        return JSONResponse(status_code=500, content=ErrorResponse(
            error_code="INTERNAL_ERROR", message=message, details={"error_id": error_id},
            request_id=getattr(request.state, "request_id", None)).model_dump(mode="json"))

    if FRONTEND_DIR.is_dir():
        app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
    else:
        @app.get("/", include_in_schema=False)
        async def landing():
            return HTMLResponse("<h1>SentinelAI API</h1><p>See <a href='/docs'>/docs</a>.</p>")

    return app


app = create_app()
