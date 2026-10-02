"""
Case & alert management
=======================

Database-backed (previously an in-memory dict that lost everything on restart).
Status changes follow an explicit state machine, SAR filing requires a
reference, and every mutation is written to the hash-chained audit log in the
same transaction.
"""

from __future__ import annotations

import uuid
from contextlib import asynccontextmanager
from datetime import timedelta
from typing import Any, AsyncIterator, Dict, List, Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from sentinelai.core import metrics
from sentinelai.core.regimes import get_regime
from sentinelai.core.time import utcnow
from sentinelai.db.session import session_scope
from sentinelai.models.database import (
    Alert,
    AlertStatus,
    Analysis,
    Case,
    CaseComment,
    CaseStatus,
    RiskLevel,
)
from sentinelai.models.schemas import CaseCreateRequest, CaseUpdateRequest
from sentinelai.services.audit import audit

S = CaseStatus
ALLOWED_TRANSITIONS = {
    S.OPEN: {S.UNDER_REVIEW, S.ESCALATED, S.SAR_FILED, S.CLOSED_NO_ACTION, S.CLOSED_FALSE_POSITIVE},
    S.UNDER_REVIEW: {S.OPEN, S.ESCALATED, S.SAR_FILED, S.CLOSED_NO_ACTION, S.CLOSED_FALSE_POSITIVE},
    S.ESCALATED: {S.UNDER_REVIEW, S.SAR_FILED, S.CLOSED_NO_ACTION, S.CLOSED_FALSE_POSITIVE},
    S.SAR_FILED: set(),                                   # terminal: a filed report cannot be un-filed
    S.CLOSED_NO_ACTION: {S.OPEN},                         # reopen
    S.CLOSED_FALSE_POSITIVE: {S.OPEN},
}
CLOSED = {S.CLOSED_NO_ACTION, S.CLOSED_FALSE_POSITIVE}
ACTIVE = [S.OPEN.value, S.UNDER_REVIEW.value, S.ESCALATED.value]


class InvalidTransition(ValueError):
    pass


class CaseNotFound(LookupError):
    pass


@asynccontextmanager
async def _scope(session: Optional[AsyncSession]) -> AsyncIterator[AsyncSession]:
    if session is not None:
        yield session
    else:
        async with session_scope() as s:
            yield s


def new_case_number() -> str:
    return f"CASE-{utcnow().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"


class CaseManagementService:
    # ---------------------------------------------------------------- create
    async def create_case(
        self, request: CaseCreateRequest, actor: str = "system", session: Optional[AsyncSession] = None,
        report: Optional[Dict[str, Any]] = None, ai_summary: Optional[str] = None,
        ai_recommendation: Optional[str] = None, regime: Optional[str] = None,
    ) -> Case:
        async with _scope(session) as s:
            now = utcnow()
            urgent = request.priority in ("HIGH", "CRITICAL") or getattr(request.priority, "value", "") in ("HIGH", "CRITICAL")
            deadline = get_regime(regime).filing_deadline(now)
            case = Case(
                case_number=new_case_number(), title=request.title, description=request.description,
                priority=getattr(request.priority, "value", request.priority), assigned_to=request.assigned_to,
                analysis_id=request.analysis_id, ai_summary=ai_summary, ai_recommendation=ai_recommendation,
                report=report, review_deadline=now + timedelta(hours=24 if urgent else 72),
                report_deadline=deadline,
            )
            s.add(case)
            await s.flush()
            if request.alert_ids:
                alerts = (await s.execute(select(Alert).where(Alert.id.in_(request.alert_ids)))).scalars().all()
                for a in alerts:
                    a.case_id = case.id
            s.add(CaseComment(case_id=case.id, author="SYSTEM", comment_type="SYSTEM",
                              content=f"Case created: {request.title}"))
            await audit.append(s, actor=actor, action="case.create", entity_type="case", entity_id=str(case.id),
                               payload={"case_number": case.case_number, "priority": case.priority,
                                        "analysis_id": str(request.analysis_id) if request.analysis_id else None})
            metrics.CASES_CREATED.inc()
            await s.flush()
            return case

    # ----------------------------------------------------------------- read
    async def get_case(self, case_id: uuid.UUID, session: Optional[AsyncSession] = None) -> Optional[Case]:
        async with _scope(session) as s:
            return await s.get(Case, case_id)

    async def list_cases(
        self, status: Optional[str] = None, priority: Optional[str] = None, assigned_to: Optional[str] = None,
        limit: int = 50, offset: int = 0, session: Optional[AsyncSession] = None,
    ) -> List[Case]:
        async with _scope(session) as s:
            q = select(Case).order_by(Case.created_at.desc())
            if status:
                q = q.where(Case.status == getattr(status, "value", status))
            if priority:
                q = q.where(Case.priority == getattr(priority, "value", priority))
            if assigned_to:
                q = q.where(Case.assigned_to == assigned_to)
            return list((await s.execute(q.limit(limit).offset(offset))).scalars().all())

    # --------------------------------------------------------------- update
    async def _require(self, s: AsyncSession, case_id: uuid.UUID) -> Case:
        case = await s.get(Case, case_id)
        if case is None:
            raise CaseNotFound(str(case_id))
        return case

    @staticmethod
    def _check_transition(case: Case, new: CaseStatus) -> None:
        current = CaseStatus(case.status)
        if new == current:
            return
        if new not in ALLOWED_TRANSITIONS[current]:
            raise InvalidTransition(f"Cannot move a case from {current.value} to {new.value}")

    async def update_case(
        self, case_id: uuid.UUID, request: CaseUpdateRequest, actor: str = "system",
        session: Optional[AsyncSession] = None,
    ) -> Case:
        async with _scope(session) as s:
            case = await self._require(s, case_id)
            changes: Dict[str, Any] = {}
            if request.status is not None:
                new = CaseStatus(getattr(request.status, "value", request.status))
                self._check_transition(case, new)
                if new == CaseStatus.SAR_FILED:
                    reference = request.sar_reference or case.sar_reference
                    if not reference:
                        raise InvalidTransition("Filing a report requires sar_reference")
                    case.sar_filed, case.sar_reference, case.sar_filed_at = True, reference, utcnow()
                if new in CLOSED or new == CaseStatus.SAR_FILED:
                    case.closed_at = utcnow()
                elif new == CaseStatus.OPEN:
                    case.closed_at = None
                if new.value != case.status:
                    changes["status"] = [case.status, new.value]
                case.status = new.value
            if request.priority is not None:
                new_priority = getattr(request.priority, "value", request.priority)
                if new_priority != case.priority:
                    changes["priority"] = [case.priority, new_priority]
                case.priority = new_priority
            if request.assigned_to is not None and request.assigned_to != case.assigned_to:
                changes["assigned_to"] = [case.assigned_to, request.assigned_to]
                case.assigned_to = request.assigned_to
            if request.investigation_notes is not None:
                case.investigation_notes = request.investigation_notes
                changes["investigation_notes"] = "updated"
            case.updated_at = utcnow()
            if changes:
                s.add(CaseComment(case_id=case.id, author=actor, comment_type="SYSTEM", content=f"Case updated: {changes}"))
                await audit.append(s, actor=actor, action="case.update", entity_type="case",
                                   entity_id=str(case.id), payload=changes)
            await s.flush()
            return case

    async def assign_case(self, case_id, assignee: str, actor: str = "system", session=None) -> Case:
        return await self.update_case(case_id, CaseUpdateRequest(assigned_to=assignee), actor, session)

    async def escalate_case(self, case_id, reason: str, actor: str = "system", session=None) -> Case:
        async with _scope(session) as s:
            case = await self._require(s, case_id)
            self._check_transition(case, CaseStatus.ESCALATED)
            old = case.status
            case.status, case.priority, case.updated_at = CaseStatus.ESCALATED.value, RiskLevel.HIGH.value, utcnow()
            s.add(CaseComment(case_id=case.id, author=actor, comment_type="ESCALATION",
                              content=f"Case escalated by {actor}. Reason: {reason}"))
            await audit.append(s, actor=actor, action="case.escalate", entity_type="case", entity_id=str(case.id),
                               payload={"from": old, "reason": reason})
            await s.flush()
            return case

    async def file_sar(self, case_id, sar_reference: str, actor: str = "system", session=None) -> Case:
        return await self.update_case(
            case_id, CaseUpdateRequest(status="SAR_FILED", sar_reference=sar_reference), actor, session)

    async def close_case(self, case_id, status: CaseStatus, reason: str, actor: str = "system", session=None) -> Case:
        status = CaseStatus(getattr(status, "value", status))
        if status not in CLOSED and status != CaseStatus.SAR_FILED:
            raise InvalidTransition("Invalid closing status")
        async with _scope(session) as s:
            case = await self._require(s, case_id)
            self._check_transition(case, status)
            if status == CaseStatus.SAR_FILED and not case.sar_reference:
                raise InvalidTransition("Filing a report requires sar_reference; use the SAR endpoint")
            case.status, case.closed_at, case.updated_at = status.value, utcnow(), utcnow()
            s.add(CaseComment(case_id=case.id, author=actor, comment_type="DECISION",
                              content=f"Case closed by {actor}. Status: {status.value}. Reason: {reason}"))
            await audit.append(s, actor=actor, action="case.close", entity_type="case", entity_id=str(case.id),
                               payload={"status": status.value, "reason": reason})
            await s.flush()
            return case

    # ------------------------------------------------------------- comments
    async def add_comment(self, case_id, content: str, comment_type: str, actor: str, session=None) -> CaseComment:
        async with _scope(session) as s:
            case = await self._require(s, case_id)
            comment = CaseComment(case_id=case.id, author=actor, content=content, comment_type=comment_type)
            s.add(comment)
            case.updated_at = utcnow()
            await audit.append(s, actor=actor, action="case.comment", entity_type="case", entity_id=str(case.id),
                               payload={"type": comment_type, "length": len(content)})
            await s.flush()
            return comment

    async def get_comments(self, case_id, session=None) -> List[CaseComment]:
        async with _scope(session) as s:
            await self._require(s, case_id)
            return list((await s.execute(
                select(CaseComment).where(CaseComment.case_id == case_id).order_by(CaseComment.created_at))).scalars().all())

    # ------------------------------------------------------------ dashboard
    async def dashboard_metrics(self, session: Optional[AsyncSession] = None) -> Dict[str, Any]:
        async with _scope(session) as s:
            now = utcnow()
            day = now - timedelta(hours=24)
            month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

            async def count(*conditions) -> int:
                return (await s.execute(select(func.count()).select_from(Case).where(*conditions))).scalar_one()

            a24 = (await s.execute(select(Analysis.risk_level, Analysis.risk_score).where(Analysis.created_at >= day))).all()
            scores = [r.risk_score for r in a24]
            by_status = dict((await s.execute(select(Case.status, func.count()).group_by(Case.status))).all())
            distribution = {lvl: 0 for lvl in ("LOW", "MEDIUM", "HIGH", "CRITICAL")}
            for r in a24:
                distribution[r.risk_level] = distribution.get(r.risk_level, 0) + 1
            high = distribution["HIGH"] + distribution["CRITICAL"]
            return {
                "total_transactions_24h": len(a24),
                "suspicious_transactions_24h": high,
                "open_cases": by_status.get(S.OPEN.value, 0),
                "pending_review": by_status.get(S.UNDER_REVIEW.value, 0) + by_status.get(S.ESCALATED.value, 0),
                "sars_filed_mtd": await count(Case.sar_filed_at >= month_start),
                "average_risk_score": round(sum(scores) / len(scores), 1) if scores else 0.0,
                "high_risk_percentage": round(100 * high / len(a24), 1) if a24 else 0.0,
                "overdue_cases": await count(Case.status.in_(ACTIVE), Case.review_deadline < now),
                "risk_distribution": distribution,
                "cases_by_status": by_status,
            }


class AlertService:
    async def list_alerts(self, status: Optional[str] = None, alert_type: Optional[str] = None,
                          severity: Optional[str] = None, limit: int = 50, offset: int = 0,
                          session: Optional[AsyncSession] = None) -> List[Alert]:
        async with _scope(session) as s:
            q = select(Alert).order_by(Alert.created_at.desc())
            if status:
                q = q.where(Alert.status == status)
            if alert_type:
                q = q.where(Alert.alert_type == alert_type)
            if severity:
                q = q.where(Alert.severity == severity)
            return list((await s.execute(q.limit(limit).offset(offset))).scalars().all())

    async def triage(self, alert_id: uuid.UUID, status: AlertStatus, actor: str, session=None) -> Alert:
        async with _scope(session) as s:
            alert = await s.get(Alert, alert_id)
            if alert is None:
                raise CaseNotFound(str(alert_id))
            old = alert.status
            alert.status = status.value
            alert.acknowledged_by, alert.acknowledged_at = actor, utcnow()
            await audit.append(s, actor=actor, action="alert.triage", entity_type="alert", entity_id=str(alert.id),
                               payload={"from": old, "to": status.value})
            await s.flush()
            return alert
