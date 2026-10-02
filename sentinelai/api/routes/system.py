"""Health, metrics and public reference data."""

from __future__ import annotations

from fastapi import APIRouter, Response

from sentinelai.core import metrics
from sentinelai.core.config import settings
from sentinelai.core.jurisdictions import get_jurisdictions
from sentinelai.core.regimes import REGIMES
from sentinelai.core.time import utcnow
from sentinelai.db import session as db
from sentinelai.engine.pep import get_pep_screener
from sentinelai.engine.sanctions import get_screener
from sentinelai.engine.typologies import TYPOLOGIES
from sentinelai.models.schemas import HealthResponse
from sentinelai.services.scenarios import load_scenarios, scenario_request

router = APIRouter()


@router.get("/health", response_model=HealthResponse, tags=["System"], summary="Health check")
async def health() -> HealthResponse:
    """Real dependency checks (previously hard-coded strings)."""
    from sentinelai.core.cache import MemoryCache, get_cache

    db_ok = await db.ping()
    screener = get_screener().info
    deps = {
        "database": {"status": "connected" if db_ok else "unavailable", "backend": "sqlite" if settings.database.is_sqlite else "postgresql"},
        "cache": "memory" if isinstance(get_cache(), MemoryCache) else "redis",
        "llm": {"provider": settings.llm.provider, "configured": settings.llm.api_key_configured,
                "model": settings.llm.groq_model if settings.llm.provider == "groq" else settings.llm.huggingface_model},
        "web_search": "enabled" if settings.llm.web_search_enabled else "disabled (privacy default)",
        "sanctions_list": {"source": screener["source"], "entries": screener["entries"], "as_of": screener["as_of"],
                           "synthetic_demo_data": screener["synthetic"]},
        "jurisdiction_data_as_of": get_jurisdictions().as_of,
        "regime": settings.risk.regime,
        "auth": "api-keys" if settings.api.api_keys else ("public-demo" if settings.api.public_demo else "open-dev"),
    }
    return HealthResponse(status="healthy" if db_ok else "degraded", version=settings.app_version,
                          environment=settings.environment, timestamp=utcnow(), dependencies=deps)


@router.get("/api", tags=["System"], summary="API root")
async def root():
    return {"name": settings.app_name, "version": settings.app_version, "documentation": "/docs",
            "health": "/health", "metrics": "/metrics", "frontend": "/"}


@router.get("/metrics", tags=["System"], summary="Prometheus metrics", include_in_schema=False)
async def prometheus_metrics():
    if not settings.monitoring.metrics_enabled:
        return Response(status_code=404)
    body, content_type = metrics.render()
    return Response(content=body, media_type=content_type)


@router.get("/api/v1/reference/jurisdictions", tags=["Reference"], summary="Jurisdiction risk data (single source of truth)")
async def reference_jurisdictions():
    return get_jurisdictions().as_dict()


@router.get("/api/v1/reference/regimes", tags=["Reference"], summary="Regulatory regime profiles")
async def reference_regimes():
    return {"default": settings.risk.regime, "regimes": [r.as_dict() for r in REGIMES.values()]}


@router.get("/api/v1/reference/typologies", tags=["Reference"], summary="Money-laundering typology catalogue")
async def reference_typologies():
    return TYPOLOGIES


@router.get("/api/v1/reference/scenarios", tags=["Reference"], summary="Demo scenarios (fresh timestamps)")
async def reference_scenarios():
    return [{"id": s["id"], "title": s["scenario"], "description": s["description"], "regime": s.get("regime"),
             "request": scenario_request(s)} for s in load_scenarios()]


@router.get("/api/v1/reference/screening-lists", tags=["Reference"], summary="Loaded sanctions/PEP list metadata")
async def reference_lists():
    return {"sanctions": get_screener().info, "pep": get_pep_screener().watchlist.info}
