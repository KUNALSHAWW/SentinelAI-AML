"""Transaction analysis endpoints."""

from __future__ import annotations

import asyncio
import json
import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse

from sentinelai.api.deps import get_analysis_service
from sentinelai.core.config import settings
from sentinelai.core.logging import get_logger
from sentinelai.core.security import Principal, require
from sentinelai.engine.sanctions import get_screener
from sentinelai.models.schemas import (
    AnalysisRequest, AnalysisResponse, BatchAnalysisRequest, BatchAnalysisResponse,
)
from sentinelai.services.analysis import AnalysisNotFound

logger = get_logger(__name__)
router = APIRouter(prefix="/api/v1", tags=["Analysis"])


@router.post("/analyze", response_model=AnalysisResponse, summary="Analyze a transaction")
async def analyze(request: AnalysisRequest, principal: Principal = Depends(require("analyst", allow_demo=True))):
    """Full analysis: deterministic engine (sanctions, PEP, geography, behaviour, graph, crypto, trade) plus optional
    AI research, with an explainable score, typologies, alerts, an optional SAR/STR draft and a tamper-evident audit entry."""
    return await get_analysis_service().analyze_transaction(request, principal)


@router.post("/analyze/rules", response_model=AnalysisResponse, summary="Deterministic-only analysis (no LLM)")
async def analyze_rules(request: AnalysisRequest, principal: Principal = Depends(require("analyst", allow_demo=True))):
    """Same engine and thresholds as ``/analyze`` with AI research forced off - fast and always available."""
    request = request.model_copy(update={"enable_llm_analysis": False})
    return await get_analysis_service().analyze_transaction(request, principal)


@router.post("/analyze/stream", summary="Analyze with Server-Sent-Event progress")
async def analyze_stream(request: AnalysisRequest, http_request: Request,
                         principal: Principal = Depends(require("analyst", allow_demo=True))):
    async def events():
        queue: asyncio.Queue = asyncio.Queue()

        async def progress(step: str):
            await queue.put(("progress", step))

        async def run():
            try:
                result = await get_analysis_service().analyze_transaction(request, principal, progress_callback=progress)
                await queue.put(("result", result))
            except Exception:
                error_id = uuid.uuid4().hex[:12]
                logger.error("Streaming analysis failed (error_id=%s)", error_id, exc_info=True)
                await queue.put(("error", error_id))

        task = asyncio.create_task(run())
        try:
            while True:
                try:
                    kind, payload = await asyncio.wait_for(queue.get(), timeout=15)
                except asyncio.TimeoutError:
                    if await http_request.is_disconnected():
                        break
                    yield ": keep-alive\n\n"
                    continue
                if kind == "progress":
                    yield f"data: {json.dumps({'type': 'progress', 'step': payload})}\n\n"
                elif kind == "result":
                    yield f"data: {json.dumps({'type': 'result', 'result': json.loads(payload.model_dump_json())})}\n\n"
                    break
                else:
                    yield f"data: {json.dumps({'type': 'error', 'message': 'Analysis failed', 'error_id': payload})}\n\n"
                    break
        finally:
            if not task.done():
                task.cancel()                       # client went away: stop burning LLM budget

    return StreamingResponse(events(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@router.post("/analyze/batch", response_model=BatchAnalysisResponse, summary="Analyze many transactions")
async def analyze_batch(request: BatchAnalysisRequest, principal: Principal = Depends(require("analyst"))):
    """Per-item results - failures are reported with their index, never silently dropped."""
    return await get_analysis_service().batch_analyze(request.transactions, principal, batch_id=request.batch_id)


@router.get("/analyses", summary="List recent analyses")
async def list_analyses(limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0),
                        min_score: Optional[int] = Query(None, ge=0, le=100),
                        principal: Principal = Depends(require("viewer"))):
    return await get_analysis_service().list_analyses(limit, offset, min_score)


@router.get("/analyses/{analysis_id}", response_model=AnalysisResponse, summary="Retrieve a stored analysis")
async def get_analysis(analysis_id: uuid.UUID, principal: Principal = Depends(require("viewer"))):
    try:
        return await get_analysis_service().get_analysis(analysis_id)
    except AnalysisNotFound:
        raise HTTPException(status_code=404, detail="Analysis not found")


@router.get("/analyze/metrics", summary="Engine/runtime facts")
async def analysis_metrics(principal: Principal = Depends(require("viewer"))):
    from sentinelai.agents.base import LLMFactory
    return {
        "llm": {"provider": settings.llm.provider, "configured": LLMFactory.available(),
                "web_search_enabled": settings.llm.web_search_enabled, "max_uplift_points": settings.llm.max_uplift},
        "sanctions_list": get_screener().info,
        "thresholds": {"medium": settings.risk.medium_risk_threshold, "high": settings.risk.high_risk_threshold,
                       "critical": settings.risk.critical_risk_threshold, "report": settings.risk.sar_score_threshold},
    }
