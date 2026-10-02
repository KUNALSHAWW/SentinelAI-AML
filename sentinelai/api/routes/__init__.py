"""API routers."""

from fastapi import APIRouter

from sentinelai.api.routes import analysis, audit_routes, cases, system

router = APIRouter()
router.include_router(system.router)
router.include_router(analysis.router)
router.include_router(cases.router)
router.include_router(audit_routes.router)

__all__ = ["router"]
