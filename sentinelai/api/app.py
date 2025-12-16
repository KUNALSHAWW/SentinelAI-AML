"""
SentinelAI FastAPI Application
==============================

Main FastAPI application setup with middleware, 
exception handlers, and configuration.
"""

from contextlib import asynccontextmanager
from typing import AsyncGenerator
from pathlib import Path
import time

from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse, FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware

from sentinelai.core.config import settings
from sentinelai.core.logging import get_logger, setup_logging
from sentinelai.api.routes import router
from sentinelai.models.schemas import ErrorResponse

logger = get_logger(__name__)

# Frontend directory path
FRONTEND_DIR = Path(__file__).parent.parent.parent / "frontend"


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Middleware for request/response logging"""
    
    async def dispatch(self, request: Request, call_next):
        start_time = time.time()
        
        # Generate request ID
        request_id = request.headers.get("X-Request-ID", str(time.time()))
        
        # Log request
        logger.info(
            f"Request started",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "client_ip": request.client.host if request.client else "unknown",
            }
        )
        
        # Process request
        response = await call_next(request)
        
        # Calculate duration
        duration_ms = (time.time() - start_time) * 1000
        
        # Log response
        logger.info(
            f"Request completed",
            extra={
                "request_id": request_id,
                "status_code": response.status_code,
                "duration_ms": round(duration_ms, 2),
            }
        )
        
        # Add headers
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Process-Time"] = str(round(duration_ms, 2))
        
        return response


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Simple rate limiting middleware"""
    
    def __init__(self, app, requests_per_minute: int = 100):
        super().__init__(app)
        self.requests_per_minute = requests_per_minute
        self._request_counts: dict = {}
    
    async def dispatch(self, request: Request, call_next):
        # Get client identifier
        client_ip = request.client.host if request.client else "unknown"
        api_key = request.headers.get(settings.api.api_key_header, "")
        client_id = f"{client_ip}:{api_key[:8]}" if api_key else client_ip
        
        # Simple minute-based rate limiting
        current_minute = int(time.time() / 60)
        key = f"{client_id}:{current_minute}"
        
        self._request_counts[key] = self._request_counts.get(key, 0) + 1
        
        if self._request_counts[key] > self.requests_per_minute:
            return JSONResponse(
                status_code=429,
                content={
                    "error_code": "RATE_LIMIT_EXCEEDED",
                    "message": f"Rate limit of {self.requests_per_minute} requests per minute exceeded",
                }
            )
        
        # Cleanup old entries
        self._cleanup_old_entries(current_minute)
        
        return await call_next(request)
    
    def _cleanup_old_entries(self, current_minute: int):
        """Remove old rate limit entries"""
        keys_to_remove = [
            k for k in self._request_counts.keys()
            if int(k.split(":")[-1]) < current_minute - 2
        ]
        for k in keys_to_remove:
            del self._request_counts[k]


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator:
    """Application lifespan handler"""
    
    # Startup
    logger.info("🚀 SentinelAI starting up...")
    
    # Initialize logging
    setup_logging(
        log_level=settings.monitoring.log_level,
        log_format=settings.monitoring.log_format,
        log_file=settings.monitoring.log_file
    )
    
    # Log configuration
    logger.info(
        f"Configuration loaded",
        extra={
            "environment": settings.environment,
            "llm_provider": settings.llm.provider,
            "api_host": settings.api.host,
            "api_port": settings.api.port,
        }
    )
    
    logger.info("✅ SentinelAI ready to serve requests")
    
    yield
    
    # Shutdown
    logger.info("👋 SentinelAI shutting down...")


def create_app() -> FastAPI:
    """
    Create and configure the FastAPI application.
    
    Returns:
        Configured FastAPI application instance
    """
    
    app = FastAPI(
        title="SentinelAI",
        description="""
# 🛡️ SentinelAI - Financial Crime Intelligence Platform

Enterprise-grade Anti-Money Laundering (AML) detection system powered by 
AI and LangGraph for intelligent, graph-based transaction analysis.

## Features

- **Real-time Transaction Analysis**: Instant risk assessment with detailed reasoning
- **Multi-factor Detection**: Geographic, behavioral, sanctions, PEP, and crypto analysis
- **LLM-powered Investigation**: Chain-of-Thought and ReAct reasoning for deep analysis
- **Case Management**: Complete workflow for investigation and SAR filing
- **Regulatory Compliance**: Built for BSA/AML compliance requirements

## Authentication

Use API key authentication with the `X-API-Key` header.

## Rate Limiting

Default rate limit: 100 requests per minute per API key.
        """,
        version=settings.app_version,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )
    
    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.api.cors_origins,
        allow_credentials=settings.api.cors_allow_credentials,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Add GZip compression
    app.add_middleware(GZipMiddleware, minimum_size=1000)
    
    # Add request logging
    app.add_middleware(RequestLoggingMiddleware)
    
    # Add rate limiting
    app.add_middleware(
        RateLimitMiddleware,
        requests_per_minute=settings.api.rate_limit_requests
    )
    
    # =====================
    # Serve Frontend (BEFORE API routes)
    # =====================
    
    @app.get("/", response_class=HTMLResponse, include_in_schema=False)
    async def serve_frontend():
        """Serve the main frontend page"""
        index_file = FRONTEND_DIR / "index.html"
        if index_file.exists():
            return FileResponse(index_file)
        return HTMLResponse("<h1>SentinelAI API</h1><p>Visit <a href='/docs'>/docs</a> for API documentation</p>")
    
    @app.get("/app.js", include_in_schema=False)
    async def serve_js():
        """Serve frontend JavaScript"""
        js_file = FRONTEND_DIR / "app.js"
        if js_file.exists():
            return FileResponse(js_file, media_type="application/javascript")
        raise HTTPException(status_code=404, detail="File not found")
    
    @app.get("/styles.css", include_in_schema=False)
    async def serve_css():
        """Serve frontend CSS"""
        css_file = FRONTEND_DIR / "styles.css"
        if css_file.exists():
            return FileResponse(css_file, media_type="text/css")
        raise HTTPException(status_code=404, detail="File not found")
    
    # Include API routers (after frontend routes)
    app.include_router(router)
    
    # Exception handlers
    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        return JSONResponse(
            status_code=exc.status_code,
            content=ErrorResponse(
                error_code=f"HTTP_{exc.status_code}",
                message=exc.detail,
                request_id=request.headers.get("X-Request-ID")
            ).model_dump()
        )
    
    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception):
        logger.error(
            f"Unhandled exception: {str(exc)}",
            exc_info=True,
            extra={"path": request.url.path}
        )
        
        if settings.api.debug:
            detail = str(exc)
        else:
            detail = "An internal error occurred"
        
        return JSONResponse(
            status_code=500,
            content=ErrorResponse(
                error_code="INTERNAL_ERROR",
                message=detail,
                request_id=request.headers.get("X-Request-ID")
            ).model_dump()
        )
    
    return app


# Create app instance for uvicorn
app = create_app()
