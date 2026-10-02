"""Tamper-evident audit trail endpoints."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query

from sentinelai.core import metrics
from sentinelai.core.security import Principal, require
from sentinelai.db.session import session_scope
from sentinelai.models.schemas import AuditVerifyResponse
from sentinelai.services.audit import audit

router = APIRouter(prefix="/api/v1/audit", tags=["Audit"])


@router.get("/head", summary="Current chain head - publish/anchor this externally")
async def head(principal: Principal = Depends(require("viewer"))):
    async with session_scope() as s:
        info = await audit.head(s)
    metrics.AUDIT_ENTRIES.set(info["entries"])
    return info


@router.get("/verify", response_model=AuditVerifyResponse, summary="Recompute the entire hash chain")
async def verify(principal: Principal = Depends(require("viewer"))):
    async with session_scope() as s:
        result = await audit.verify(s)
    metrics.AUDIT_ENTRIES.set(result["entries"])
    return result


@router.get("/entries", summary="Browse audit entries")
async def entries(entity_type: Optional[str] = None, entity_id: Optional[str] = None,
                  limit: int = Query(100, ge=1, le=500), offset: int = Query(0, ge=0),
                  principal: Principal = Depends(require("admin"))):
    async with session_scope() as s:
        rows = await audit.entries(s, entity_type, entity_id, limit, offset)
    return [{"seq": r.seq, "timestamp": r.timestamp, "actor": r.actor, "action": r.action,
             "entity_type": r.entity_type, "entity_id": r.entity_id, "payload": r.payload,
             "prev_hash": r.prev_hash, "hash": r.hash} for r in rows]
