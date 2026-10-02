"""Case state machine, comments, alerts and audit coupling (service layer)."""

import pytest

from sentinelai.db.session import session_scope
from sentinelai.models.database import AlertStatus, CaseStatus
from sentinelai.models.schemas import CaseCreateRequest, CaseUpdateRequest
from sentinelai.services.audit import audit
from sentinelai.services.case_management import AlertService, CaseManagementService, CaseNotFound, InvalidTransition

svc = CaseManagementService()


async def new_case(**kw):
    return await svc.create_case(CaseCreateRequest(title="T", priority=kw.pop("priority", "MEDIUM"), **kw), actor="bob")


async def test_create_sets_deadlines_and_system_comment(db):
    c = await new_case(priority="HIGH")
    assert c.status == "OPEN" and c.case_number.startswith("CASE-") and c.review_deadline and c.report_deadline
    comments = await svc.get_comments(c.id)
    assert comments[0].author == "SYSTEM"
    high_hours = (c.review_deadline - c.created_at).total_seconds() / 3600
    low = await new_case(priority="LOW")
    assert high_hours < (low.review_deadline - low.created_at).total_seconds() / 3600


async def test_valid_path_open_review_escalate_file(db):
    c = await new_case()
    c = await svc.update_case(c.id, CaseUpdateRequest(status="UNDER_REVIEW"), "bob")
    c = await svc.escalate_case(c.id, "needs seniors", "bob")
    assert c.status == "ESCALATED" and c.priority == "HIGH"
    c = await svc.file_sar(c.id, "BSA-2026-0001", "bob")
    assert c.status == "SAR_FILED" and c.sar_filed and c.sar_reference == "BSA-2026-0001" and c.closed_at


async def test_filed_case_is_terminal(db):
    c = await svc.file_sar((await new_case()).id, "REF1", "bob")
    for target in ("OPEN", "UNDER_REVIEW", "CLOSED_NO_ACTION"):
        with pytest.raises(InvalidTransition):
            await svc.update_case(c.id, CaseUpdateRequest(status=target), "bob")


async def test_sar_requires_reference(db):
    c = await new_case()
    with pytest.raises(InvalidTransition):
        await svc.update_case(c.id, CaseUpdateRequest(status="SAR_FILED"), "bob")
    with pytest.raises(InvalidTransition):
        await svc.close_case(c.id, CaseStatus.SAR_FILED, "x", "bob")
    c = await svc.update_case(c.id, CaseUpdateRequest(status="SAR_FILED", sar_reference="R9"), "bob")
    assert c.sar_filed


async def test_close_and_reopen(db):
    c = await new_case()
    c = await svc.close_case(c.id, CaseStatus.CLOSED_FALSE_POSITIVE, "benign", "bob")
    assert c.status == "CLOSED_FALSE_POSITIVE" and c.closed_at
    c = await svc.update_case(c.id, CaseUpdateRequest(status="OPEN"), "bob")
    assert c.status == "OPEN" and c.closed_at is None


async def test_invalid_close_status_and_unknown_case(db):
    c = await new_case()
    with pytest.raises(InvalidTransition):
        await svc.close_case(c.id, CaseStatus.ESCALATED, "x", "bob")
    import uuid
    with pytest.raises(CaseNotFound):
        await svc.update_case(uuid.uuid4(), CaseUpdateRequest(priority="LOW"), "bob")


async def test_every_mutation_is_audited_and_chain_stays_valid(db):
    c = await new_case()
    await svc.assign_case(c.id, "carol", "bob")
    await svc.add_comment(c.id, "looked at it", "NOTE", "carol")
    await svc.escalate_case(c.id, "r", "carol")
    async with session_scope() as s:
        actions = [e.action for e in await audit.entries(s, limit=20)]
        assert (await audit.verify(s))["valid"]
    assert {"case.create", "case.update", "case.comment", "case.escalate"} <= set(actions)


async def test_filters_and_pagination(db):
    for p in ("LOW", "HIGH", "HIGH"):
        await new_case(priority=p)
    assert len(await svc.list_cases(priority="HIGH")) == 2
    assert len(await svc.list_cases(limit=2)) == 2 and len(await svc.list_cases(limit=2, offset=2)) == 1
    assert await svc.list_cases(assigned_to="nobody") == []


async def test_dashboard_counts_overdue_and_status(db):
    from datetime import timedelta

    from sentinelai.core.time import utcnow
    c = await new_case()
    async with session_scope() as s:
        row = await svc.get_case(c.id, s)
        row.review_deadline = utcnow() - timedelta(hours=1)
    m = await svc.dashboard_metrics()
    assert m["open_cases"] == 1 and m["overdue_cases"] == 1 and m["cases_by_status"] == {"OPEN": 1}


async def test_alert_triage_is_audited(db):
    from sentinelai.models.database import Alert
    async with session_scope() as s:
        a = Alert(alert_type="STRUCTURING", severity="HIGH", title="t", signal_codes=["X"])
        s.add(a)
        await s.flush()
        alert_id = a.id
    out = await AlertService().triage(alert_id, AlertStatus.FALSE_POSITIVE, "bob")
    assert out.status == "FALSE_POSITIVE" and out.acknowledged_by == "bob"
    assert [x.status for x in await AlertService().list_alerts(status="FALSE_POSITIVE")] == ["FALSE_POSITIVE"]
