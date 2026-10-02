"""Cases, alerts and dashboard."""

from __future__ import annotations

import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import PlainTextResponse

from sentinelai.api.deps import get_alert_service, get_case_service
from sentinelai.core.security import Principal, require
from sentinelai.models.database import AlertStatus
from sentinelai.models.schemas import (
    AlertResponse,
    AlertTypeEnum,
    CaseCommentRequest,
    CaseCreateRequest,
    CaseResponse,
    CaseStatusEnum,
    CaseUpdateRequest,
    CommentResponse,
    DashboardMetrics,
    RiskLevelEnum,
)
from sentinelai.services import reporting
from sentinelai.services.case_management import CaseNotFound, InvalidTransition

router = APIRouter(prefix="/api/v1")


async def _call(coro):
    try:
        return await coro
    except CaseNotFound:
        raise HTTPException(status_code=404, detail="Not found")
    except InvalidTransition as exc:
        raise HTTPException(status_code=409, detail=str(exc))


# --------------------------------------------------------------------------- cases
@router.post("/cases", response_model=CaseResponse, tags=["Cases"], summary="Create case")
async def create_case(request: CaseCreateRequest, principal: Principal = Depends(require("analyst"))):
    return await get_case_service().create_case(request, actor=principal.name)


@router.get("/cases", response_model=List[CaseResponse], tags=["Cases"], summary="List cases")
async def list_cases(status: Optional[CaseStatusEnum] = None, priority: Optional[RiskLevelEnum] = None,
                     assigned_to: Optional[str] = None, limit: int = Query(50, ge=1, le=100), offset: int = Query(0, ge=0),
                     principal: Principal = Depends(require("viewer"))):
    return await get_case_service().list_cases(status, priority, assigned_to, limit, offset)


@router.get("/cases/{case_id}", response_model=CaseResponse, tags=["Cases"], summary="Get case")
async def get_case(case_id: uuid.UUID, principal: Principal = Depends(require("viewer"))):
    case = await get_case_service().get_case(case_id)
    if case is None:
        raise HTTPException(status_code=404, detail="Case not found")
    return case


@router.patch("/cases/{case_id}", response_model=CaseResponse, tags=["Cases"], summary="Update case (state machine enforced)")
async def update_case(case_id: uuid.UUID, request: CaseUpdateRequest, principal: Principal = Depends(require("analyst"))):
    return await _call(get_case_service().update_case(case_id, request, actor=principal.name))


@router.post("/cases/{case_id}/assign", response_model=CaseResponse, tags=["Cases"], summary="Assign case")
async def assign_case(case_id: uuid.UUID, assignee: str = Query(..., min_length=1, max_length=100),
                      principal: Principal = Depends(require("analyst"))):
    return await _call(get_case_service().assign_case(case_id, assignee, actor=principal.name))


@router.post("/cases/{case_id}/escalate", response_model=CaseResponse, tags=["Cases"], summary="Escalate case")
async def escalate_case(case_id: uuid.UUID, reason: str = Query(..., min_length=1, max_length=1000),
                        principal: Principal = Depends(require("analyst"))):
    return await _call(get_case_service().escalate_case(case_id, reason, actor=principal.name))


@router.post("/cases/{case_id}/sar", response_model=CaseResponse, tags=["Cases"], summary="Mark SAR/STR filed")
async def file_sar(case_id: uuid.UUID, sar_reference: str = Query(..., min_length=1, max_length=100),
                   principal: Principal = Depends(require("analyst"))):
    return await _call(get_case_service().file_sar(case_id, sar_reference, actor=principal.name))


@router.post("/cases/{case_id}/close", response_model=CaseResponse, tags=["Cases"], summary="Close case")
async def close_case(case_id: uuid.UUID, status: CaseStatusEnum = Query(...), reason: str = Query(..., min_length=1, max_length=1000),
                     principal: Principal = Depends(require("analyst"))):
    return await _call(get_case_service().close_case(case_id, status, reason, actor=principal.name))


@router.post("/cases/{case_id}/comments", response_model=CommentResponse, tags=["Cases"], summary="Add comment")
async def add_comment(case_id: uuid.UUID, request: CaseCommentRequest, principal: Principal = Depends(require("analyst"))):
    return await _call(get_case_service().add_comment(case_id, request.content, request.comment_type, principal.name))


@router.get("/cases/{case_id}/comments", response_model=List[CommentResponse], tags=["Cases"], summary="List comments")
async def get_comments(case_id: uuid.UUID, principal: Principal = Depends(require("viewer"))):
    return await _call(get_case_service().get_comments(case_id))


@router.get("/cases/{case_id}/report", tags=["Cases"], summary="SAR/STR draft (json or markdown)")
async def case_report(case_id: uuid.UUID, format: str = Query("json", pattern="^(json|markdown)$"),
                      principal: Principal = Depends(require("viewer"))):
    case = await get_case_service().get_case(case_id)
    if case is None:
        raise HTTPException(status_code=404, detail="Case not found")
    if not case.report:
        raise HTTPException(status_code=404, detail="No report draft is attached to this case")
    if format == "markdown":
        return PlainTextResponse(reporting.to_markdown(case.report), media_type="text/markdown")
    return case.report


# --------------------------------------------------------------------------- alerts
@router.get("/alerts", response_model=List[AlertResponse], tags=["Alerts"], summary="List alerts")
async def list_alerts(status: Optional[str] = Query(None, pattern="^(OPEN|ACKNOWLEDGED|FALSE_POSITIVE|ESCALATED)$"),
                      alert_type: Optional[AlertTypeEnum] = None, severity: Optional[RiskLevelEnum] = None,
                      limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0),
                      principal: Principal = Depends(require("viewer"))):
    return await get_alert_service().list_alerts(
        status, alert_type.value if alert_type else None, severity.value if severity else None, limit, offset)


@router.patch("/alerts/{alert_id}", response_model=AlertResponse, tags=["Alerts"], summary="Triage an alert")
async def triage_alert(alert_id: uuid.UUID, status: AlertStatus = Query(...),
                       principal: Principal = Depends(require("analyst"))):
    return await _call(get_alert_service().triage(alert_id, status, principal.name))


# ------------------------------------------------------------------------ dashboard
@router.get("/dashboard/metrics", response_model=DashboardMetrics, tags=["Dashboard"], summary="Dashboard metrics")
async def dashboard_metrics(principal: Principal = Depends(require("viewer"))):
    return DashboardMetrics(**await get_case_service().dashboard_metrics())
