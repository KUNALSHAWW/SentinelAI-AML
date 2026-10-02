"""
Analysis service
================

Orchestrates one analysis end to end:

    request -> engine input -> (persisted graph neighbourhood) -> LangGraph pipeline
            -> alerts + case + audit entry + persisted graph edges -> response

Everything that changes state happens in a single database transaction, and the
response says exactly how it was produced (``mode``, ``llm_status``, ``warnings``).
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import time
import uuid
from datetime import timedelta
from typing import Any, Dict, List, Optional, Set

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from sentinelai.agents.orchestrator import AMLOrchestrator
from sentinelai.core import metrics
from sentinelai.core.config import settings
from sentinelai.core.logging import get_logger
from sentinelai.core.regimes import get_regime
from sentinelai.core.security import Principal
from sentinelai.core.time import utcnow
from sentinelai.db.session import session_scope
from sentinelai.engine import build_input
from sentinelai.engine.graph import edges_from_input
from sentinelai.engine.scoring import ScoreResult
from sentinelai.engine.types import Edge, Signal
from sentinelai.models.database import Alert, Analysis, GraphEdge
from sentinelai.models.schemas import (
    AlertResponse,
    AnalysisRequest,
    AnalysisResponse,
    BatchAnalysisResponse,
    BatchItemResult,
    CaseCreateRequest,
    CaseResponse,
    Explanation,
    LLMAnalysisResult,
    RiskAssessmentResult,
    RiskFactor,
    RiskLevelEnum,
)
from sentinelai.services.audit import audit, canonical
from sentinelai.services.case_management import CaseManagementService

logger = get_logger(__name__)

_SEVERITY_RANK = {"LOW": 0, "MEDIUM": 1, "HIGH": 2, "CRITICAL": 3}
GRAPH_LOOKBACK = timedelta(days=30)
GRAPH_EDGE_LIMIT = 400


class AnalysisNotFound(LookupError):
    pass


class AnalysisService:
    def __init__(self, orchestrator: Optional[AMLOrchestrator] = None, cases: Optional[CaseManagementService] = None):
        self._orchestrator = orchestrator
        self.cases = cases or CaseManagementService()

    @property
    def orchestrator(self) -> AMLOrchestrator:
        if self._orchestrator is None:
            self._orchestrator = AMLOrchestrator()
        return self._orchestrator

    # --------------------------------------------------------------- graph store
    async def _load_neighbourhood(self, session: AsyncSession, focus: Set[str], now) -> List[Edge]:
        """Edges within two hops of ``focus`` seen in earlier analyses (the graph has memory)."""
        if not focus:
            return []
        since = now - GRAPH_LOOKBACK
        edges: Dict[str, Edge] = {}
        frontier = set(focus)
        for _ in range(2):
            rows = (await session.execute(
                select(GraphEdge).where(GraphEdge.timestamp >= since,
                                        or_(GraphEdge.source.in_(frontier), GraphEdge.target.in_(frontier)))
                .order_by(GraphEdge.timestamp.desc()).limit(GRAPH_EDGE_LIMIT))).scalars().all()
            nxt = set()
            for r in rows:
                e = Edge(r.source, r.target, r.amount_usd, r.timestamp, r.ref)
                edges[e.key()] = e
                nxt |= {r.source, r.target}
            frontier = nxt - focus
            if not frontier:
                break
        return list(edges.values())

    async def _persist_edges(self, session: AsyncSession, edges: List[Edge], analysis_id: uuid.UUID) -> int:
        if not edges:
            return 0
        keys = [e.key() for e in edges]
        existing = set((await session.execute(select(GraphEdge.edge_key).where(GraphEdge.edge_key.in_(keys)))).scalars())
        added = 0
        for e in edges:
            if e.key() in existing:
                continue
            session.add(GraphEdge(source=e.source, target=e.target, amount_usd=e.amount_usd, timestamp=e.timestamp,
                                  analysis_id=analysis_id, ref=e.ref, edge_key=e.key()))
            added += 1
        return added

    # --------------------------------------------------------------------- main
    async def analyze_transaction(
        self, request: AnalysisRequest, principal: Optional[Principal] = None, progress_callback=None,
    ) -> AnalysisResponse:
        started = time.perf_counter()
        principal = principal or Principal("system", "analyst")
        persist = request.persist and not principal.is_demo
        analysis_id = uuid.uuid4()

        tx = request.transaction.model_dump(mode="python")
        customer = request.customer.model_dump(mode="python")
        network = [n.model_dump(mode="python") for n in request.network_transactions]
        ctx = build_input(tx, customer, network, regime=request.regime,
                          confidential=request.restrict_external_lookup, enable_graph=request.enable_network_analysis)
        request_hash = hashlib.sha256(canonical(request.model_dump(mode="json", exclude={"correlation_id", "batch_id"})).encode()).hexdigest()

        # Phase 1 - short read transaction: the persisted graph neighbourhood.
        extra: List[Edge] = []
        if persist and request.enable_network_analysis:
            all_edges = edges_from_input(ctx)
            focus = {ctx.sender, ctx.receiver} | {e.source for e in all_edges} | {e.target for e in all_edges}
            async with session_scope() as session:
                extra = await self._load_neighbourhood(session, focus, ctx.timestamp)

        # Phase 2 - the pipeline (may run for a minute of LLM calls): NO database transaction is held open.
        state = await self.orchestrator.analyze(
            ctx, extra_edges=extra, research=request.enable_llm_analysis,
            confidential=request.restrict_external_lookup, progress_callback=progress_callback)

        engine, score, decision = state["engine"], state["score"], state["decision"]
        signals: List[Signal] = state["signals"]
        alerts_payload = self._derive_alerts(signals)
        mode = "hybrid" if state.get("llm_status") in ("ok", "partial") and state.get("findings") else "deterministic"

        # Phase 3 - one short write transaction: alerts, case, audit entry, analysis row and graph edges together.
        case_orm = None
        alert_rows: List[Alert] = []
        audit_info = None
        async with session_scope() as session:
            if persist:
                alert_rows = [Alert(analysis_id=analysis_id, **a) for a in alerts_payload]
                session.add_all(alert_rows)
                await session.flush()
                if decision["report_required"]:
                    regime = get_regime(ctx.regime)
                    priority = "MEDIUM" if score.level == "LOW" else score.level
                    case_orm = await self.cases.create_case(
                        CaseCreateRequest(
                            title=f"{regime.suspicious_report} review - {ctx.customer_name or 'unknown'} - score {score.score}",
                            description=state.get("summary"), priority=priority, analysis_id=analysis_id,
                            alert_ids=[a.id for a in alert_rows]),
                        actor=principal.name, session=session, report=state.get("report"),
                        ai_summary=state.get("summary"), ai_recommendation=decision["recommended_action"],
                        regime=ctx.regime)
                    if state.get("report"):
                        state["report"]["case_number"] = case_orm.case_number
                        case_orm.report = dict(state["report"])      # new object so the JSON change is persisted
                entry = await audit.append(
                    session, actor=principal.name, action="analysis.complete", entity_type="analysis",
                    entity_id=str(analysis_id),
                    payload={"risk_score": score.score, "risk_level": score.level,
                             "action": decision["recommended_action"], "report_required": decision["report_required"],
                             "mode": mode, "request_hash": request_hash, "regime": ctx.regime,
                             "signals": sorted({s.code for s in signals}),
                             "case": case_orm.case_number if case_orm else None})
                audit_info = {"seq": entry.seq, "entry_hash": entry.hash, "prev_hash": entry.prev_hash,
                              "request_hash": request_hash}

            elapsed_ms = int((time.perf_counter() - started) * 1000)
            response = self._build_response(
                analysis_id if persist else None, request, ctx, state, signals, alerts_payload, alert_rows, case_orm,
                audit_info, mode, elapsed_ms)

            if persist:
                session.add(Analysis(
                    id=analysis_id, request_hash=request_hash, customer_id=ctx.customer_id[:200],
                    customer_name=ctx.customer_name[:500], amount=ctx.amount, currency=ctx.currency,
                    amount_usd=ctx.amount_usd, transaction_type=ctx.transaction_type[:32],
                    origin_country=ctx.origin_country or None, destination_country=ctx.destination_country or None,
                    regime=ctx.regime, mode=mode, risk_score=score.score, risk_level=score.level,
                    recommended_action=decision["recommended_action"], report_required=decision["report_required"],
                    response=json.loads(response.model_dump_json())))
                await session.flush()
                await self._persist_edges(session, edges_from_input(ctx), analysis_id)

        self._record_metrics(score, mode, signals, engine, decision, elapsed_ms / 1000)
        return response

    # ------------------------------------------------------------------ helpers
    @staticmethod
    def _derive_alerts(signals: List[Signal]) -> List[Dict[str, Any]]:
        grouped: Dict[str, List[Signal]] = {}
        for s in signals:
            if s.alert_type:
                grouped.setdefault(s.alert_type, []).append(s)
        out = []
        for alert_type, group in grouped.items():
            group.sort(key=lambda s: -s.weight)
            top = group[0]
            out.append({
                "alert_type": alert_type, "severity": top.severity, "title": top.description[:100],
                "description": " | ".join(s.description for s in group)[:2000],
                "signal_codes": [s.code for s in group],
                "confidence_score": round(min(0.99, max(s.weight for s in group) + 0.2), 2),
            })
        out.sort(key=lambda a: -_SEVERITY_RANK[a["severity"]])
        return out

    def _build_response(self, analysis_id, request, ctx, state, signals, alerts_payload, alert_rows, case_orm,
                        audit_info, mode, elapsed_ms) -> AnalysisResponse:
        engine, score, decision = state["engine"], state["score"], state["decision"]
        regime = get_regime(ctx.regime)
        factors = []
        for c in score.contributions:
            factors.append(RiskFactor(
                code=c["code"], description=c["description"], severity=RiskLevelEnum(c["severity"]), score=c["points"],
                category=c["category"], typology=c.get("typology")))

        findings = [f.public() for f in state.get("findings", [])]
        llm = LLMAnalysisResult(
            summary=state.get("summary", ""),
            risk_indicators=[f.description for f in factors[:8]],
            reasoning=" -> ".join(state.get("decision_path", [])),
            confidence_score=0.9 if mode == "deterministic" else 0.8,
            recommendation=decision["recommended_action"],
            additional_context={"summary_source": state.get("summary_source"), "ai_findings": findings},
        )

        if alert_rows:
            alerts = [AlertResponse.model_validate(a) for a in alert_rows]
        else:  # not persisted: synthesize ephemeral alert objects
            alerts = [AlertResponse(id=uuid.uuid4(), alert_type=a["alert_type"], severity=a["severity"],
                                    title=a["title"], description=a["description"], risk_factors=a["signal_codes"],
                                    confidence_score=a["confidence_score"], created_at=utcnow()) for a in alerts_payload]

        report = state.get("report")
        warnings = list(state.get("warnings", []))
        j_info = engine_screening_info(engine)
        if j_info["sanctions"]["list"]["synthetic"]:
            warnings.append("Sanctions screening used the synthetic DEMO list - load OFAC data for real screening "
                            "(`sentinelai sanctions update`)")
        return AnalysisResponse(
            analysis_id=analysis_id, correlation_id=request.correlation_id, processing_time_ms=elapsed_ms,
            mode=mode, llm_status=state.get("llm_status", "disabled"), warnings=warnings,
            regime=regime.as_dict(),
            risk_assessment=RiskAssessmentResult(
                risk_score=score.score, risk_level=RiskLevelEnum(score.level), risk_factors=factors,
                decision_path=state.get("decision_path", []),
                alerts_triggered=[a["alert_type"] for a in alerts_payload]),
            explanation=Explanation(
                contributions=score.contributions, category_scores=score.category_scores,
                counterfactuals=score.counterfactuals, floor_applied=score.floor_applied,
                ai_uplift_cap=settings.llm.max_uplift),
            typologies=engine.typologies,
            screening=j_info,
            graph={"nodes": engine.graph.nodes, "edges": engine.graph.edges, "highlights": engine.graph.highlights},
            ai_findings=findings, llm_analysis=llm,
            case=CaseResponse.model_validate(case_orm) if case_orm else None, alerts=alerts,
            action_required=decision["recommended_action"] != "APPROVE",
            recommended_action=decision["recommended_action"],
            next_steps=next_steps(decision, regime, engine),
            sar_required=decision["report_required"],
            sar_deadline=regime.filing_deadline() if decision["report_required"] else None,
            report=report, audit=audit_info)

    @staticmethod
    def _record_metrics(score: ScoreResult, mode, signals, engine, decision, seconds) -> None:
        metrics.ANALYSES.labels(score.level, mode).inc()
        metrics.ANALYSIS_LATENCY.labels(mode).observe(seconds)
        for s in signals:
            metrics.SIGNALS.labels(s.code).inc()
        for m in engine.sanctions_matches:
            metrics.SANCTIONS_HITS.labels(m["level"]).inc()
        if decision["report_required"]:
            metrics.REPORTS_REQUIRED.inc()

    # -------------------------------------------------------------------- batch
    async def batch_analyze(self, requests: List[AnalysisRequest], principal: Optional[Principal] = None,
                            max_concurrent: int = 5, batch_id: Optional[str] = None) -> BatchAnalysisResponse:
        sem = asyncio.Semaphore(max_concurrent)

        async def one(i: int, req: AnalysisRequest) -> BatchItemResult:
            async with sem:
                try:
                    return BatchItemResult(index=i, status="ok", result=await self.analyze_transaction(req, principal))
                except Exception as exc:
                    logger.error("Batch item %s failed", i, exc_info=True)
                    return BatchItemResult(index=i, status="error", error=f"{type(exc).__name__}")

        items = await asyncio.gather(*[one(i, r) for i, r in enumerate(requests)])
        ok = sum(1 for i in items if i.status == "ok")
        return BatchAnalysisResponse(batch_id=batch_id, total=len(items), succeeded=ok, failed=len(items) - ok,
                                     items=list(items))

    async def get_analysis(self, analysis_id: uuid.UUID) -> Dict[str, Any]:
        async with session_scope() as session:
            row = await session.get(Analysis, analysis_id)
            if row is None:
                raise AnalysisNotFound(str(analysis_id))
            return row.response

    async def list_analyses(self, limit: int = 50, offset: int = 0, min_score: Optional[int] = None) -> List[Dict[str, Any]]:
        async with session_scope() as session:
            q = select(Analysis).order_by(Analysis.created_at.desc())
            if min_score is not None:
                q = q.where(Analysis.risk_score >= min_score)
            rows = (await session.execute(q.limit(limit).offset(offset))).scalars().all()
            return [{"analysis_id": str(r.id), "created_at": r.created_at.isoformat(), "customer_name": r.customer_name,
                     "amount_usd": r.amount_usd, "risk_score": r.risk_score, "risk_level": r.risk_level,
                     "recommended_action": r.recommended_action, "report_required": r.report_required,
                     "mode": r.mode} for r in rows]


def engine_screening_info(engine) -> Dict[str, Any]:
    return {
        "sanctions": {"list": engine.sanctions_info, "matches": engine.sanctions_matches},
        "pep": engine.pep,
        "injection_detected": bool(engine.injection_hits),
    }


def next_steps(decision: Dict[str, Any], regime, engine) -> List[str]:
    rep = regime.suspicious_report
    if decision["sanctions_confirmed"]:
        return ["Block/hold the transaction immediately", "Notify the compliance / sanctions officer",
                f"File {rep}: {regime.deadline_note}", "Preserve all related documentation",
                "Consider law-enforcement referral; do not tip off the subject"]
    action = decision["recommended_action"]
    if action == "BLOCK":
        return ["Hold the transaction pending senior review", f"Prepare the {rep} (draft attached)",
                "Escalate to the compliance officer", "Do not tip off the subject"]
    if action == "ESCALATE":
        return ["Escalate to a senior analyst", f"Review the drafted {rep} narrative", "Request source-of-funds evidence",
                "Apply enhanced due diligence"]
    if action == "REVIEW":
        return ["Assign to a compliance analyst", "Review within 24 hours", "Request additional documentation if needed",
                "Record the decision and rationale"]
    return ["No immediate action required", "Continue standard monitoring"]
