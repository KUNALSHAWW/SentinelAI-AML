"""
Tamper-evident audit trail
==========================

Every state change (analysis, case transition, SAR filing, comment) appends a
row whose hash covers the previous row's hash::

    hash_n = SHA-256( prev_hash_n || canonical_json(entry_n) )

Altering, deleting or re-ordering any historical row breaks every later hash,
which :meth:`AuditService.verify` detects by recomputation. Publishing the head
hash externally (``GET /api/v1/audit/head``) anchors the log: it proves the
history existed in that exact form at that time.

Writers are serialised per process by a lock and across processes by the
``seq`` primary key (a concurrent writer gets an IntegrityError and retries).
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import weakref
from typing import Any, Dict, List, Optional

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from sentinelai.core.time import utcnow
from sentinelai.models.database import AuditLog

GENESIS = "0" * 64
_locks: "weakref.WeakKeyDictionary[asyncio.AbstractEventLoop, asyncio.Lock]" = weakref.WeakKeyDictionary()


def _lock() -> asyncio.Lock:
    """One lock per event loop (asyncio locks are loop-affine)."""
    loop = asyncio.get_running_loop()
    if loop not in _locks:
        _locks[loop] = asyncio.Lock()
    return _locks[loop]


def canonical(payload: Dict[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str, ensure_ascii=True)


def compute_hash(prev_hash: str, seq: int, timestamp: str, actor: str, action: str,
                 entity_type: str, entity_id: str, payload_text: str) -> str:
    body = canonical({"seq": seq, "timestamp": timestamp, "actor": actor, "action": action,
                      "entity_type": entity_type, "entity_id": entity_id, "payload": payload_text})
    return hashlib.sha256(f"{prev_hash}|{body}".encode("utf-8")).hexdigest()


class AuditService:
    async def append(
        self, session: AsyncSession, *, actor: str, action: str, entity_type: str, entity_id: str,
        payload: Optional[Dict[str, Any]] = None,
    ) -> AuditLog:
        payload_text = canonical(payload or {})
        async with _lock():
            for attempt in range(5):
                head = (await session.execute(select(AuditLog).order_by(AuditLog.seq.desc()).limit(1))).scalar_one_or_none()
                seq = (head.seq + 1) if head else 1
                prev = head.hash if head else GENESIS
                timestamp = utcnow().isoformat()
                entry = AuditLog(
                    seq=seq, timestamp=timestamp, actor=actor, action=action, entity_type=entity_type,
                    entity_id=str(entity_id), payload=payload_text, prev_hash=prev,
                    hash=compute_hash(prev, seq, timestamp, actor, action, entity_type, str(entity_id), payload_text),
                )
                try:
                    async with session.begin_nested():
                        session.add(entry)
                    return entry
                except IntegrityError:        # another process took this seq - retry on the new head
                    session.expunge(entry)
                    await asyncio.sleep(0.01 * (attempt + 1))
        raise RuntimeError("Could not append audit entry after retries")

    async def head(self, session: AsyncSession) -> Dict[str, Any]:
        row = (await session.execute(select(AuditLog).order_by(AuditLog.seq.desc()).limit(1))).scalar_one_or_none()
        count = (await session.execute(select(func.count(AuditLog.seq)))).scalar_one()
        return {"entries": count, "head_hash": row.hash if row else GENESIS, "head_seq": row.seq if row else 0,
                "head_timestamp": row.timestamp if row else None}

    async def verify(self, session: AsyncSession) -> Dict[str, Any]:
        """Recompute the whole chain; report the first inconsistent row (if any)."""
        rows = (await session.execute(select(AuditLog).order_by(AuditLog.seq))).scalars().all()
        prev, expected_seq = GENESIS, 1
        for row in rows:
            if row.seq != expected_seq:
                return self._result(False, len(rows), prev, row.seq,
                                    f"sequence gap or reorder: expected {expected_seq}, found {row.seq}")
            if row.prev_hash != prev:
                return self._result(False, len(rows), prev, row.seq, "prev_hash does not match the previous entry")
            recomputed = compute_hash(row.prev_hash, row.seq, row.timestamp, row.actor, row.action,
                                      row.entity_type, row.entity_id, row.payload)
            if recomputed != row.hash:
                return self._result(False, len(rows), prev, row.seq, "entry content does not match its hash (tampered)")
            prev, expected_seq = row.hash, expected_seq + 1
        return self._result(True, len(rows), prev, None, "chain intact")

    @staticmethod
    def _result(valid: bool, n: int, head: str, bad: Optional[int], detail: str) -> Dict[str, Any]:
        return {"valid": valid, "entries": n, "head_hash": head, "first_invalid_seq": bad, "detail": detail}

    async def entries(self, session: AsyncSession, entity_type: Optional[str] = None,
                      entity_id: Optional[str] = None, limit: int = 100, offset: int = 0) -> List[AuditLog]:
        q = select(AuditLog).order_by(AuditLog.seq.desc())
        if entity_type:
            q = q.where(AuditLog.entity_type == entity_type)
        if entity_id:
            q = q.where(AuditLog.entity_id == entity_id)
        return list((await session.execute(q.limit(limit).offset(offset))).scalars().all())


audit = AuditService()
