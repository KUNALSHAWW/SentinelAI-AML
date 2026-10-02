"""
AML analysis pipeline (LangGraph)
=================================

A real :class:`langgraph.graph.StateGraph` with conditional routing::

    START -> screen -> [research?] -> score -> synthesize -> [report?] -> END

* ``screen``     deterministic engine (sanctions, PEP, geo, behaviour, graph, crypto, trade)
* ``research``   parallel LLM ReAct agents - only if requested, configured, and not already
                 conclusive (a verified sanctions match needs no web research)
* ``score``      fuses AI evidence under a hard uplift cap: **AI can raise a score, never lower it**
* ``synthesize`` analyst briefing (LLM when available, deterministic text otherwise) - narrative only
* ``report``     SAR/STR draft when a filing is warranted

Every LLM step degrades gracefully and *reports* how it degraded (``llm_status`` and
``warnings``) instead of silently falling back.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import operator
from typing import Annotated, Any, Dict, List, Optional, TypedDict

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph

from sentinelai.agents.base import LLMFactory, extract_text, strip_thinking
from sentinelai.agents.findings import AgentFinding, findings_to_signals
from sentinelai.agents.prompts import PromptTemplates
from sentinelai.agents.react_agents import AgentRunner, build_queries
from sentinelai.core.cache import get_cache
from sentinelai.core.config import settings
from sentinelai.core.logging import get_logger
from sentinelai.engine.pipeline import DetectionEngine, EngineResult
from sentinelai.engine.scoring import ScoreResult, combine_with_ai, decide
from sentinelai.engine.types import Edge, EngineInput, Signal
from sentinelai.services import reporting

logger = get_logger(__name__)

CACHE_TTL = 3600


class PipelineState(TypedDict, total=False):
    ctx: EngineInput
    extra_edges: List[Edge]
    research: bool
    confidential: bool
    engine: EngineResult
    findings: List[AgentFinding]
    signals: List[Signal]
    score: ScoreResult
    decision: Dict[str, Any]
    summary: str
    summary_source: str
    report: Optional[Dict[str, Any]]
    llm_status: str
    warnings: Annotated[List[str], operator.add]
    decision_path: Annotated[List[str], operator.add]


def llm_status_for(research: bool) -> str:
    if not research:
        return "disabled"
    return "ok" if LLMFactory.available() else "no_api_key"


class AMLOrchestrator:
    def __init__(self, engine: Optional[DetectionEngine] = None, runner: Optional[AgentRunner] = None):
        self.engine = engine or DetectionEngine()
        self.runner = runner or AgentRunner()
        self.graph = self._build_graph()

    # ------------------------------------------------------------------ graph
    def _build_graph(self):
        g = StateGraph(PipelineState)
        g.add_node("screen", self._screen)
        g.add_node("research", self._research)
        g.add_node("score", self._score)
        g.add_node("synthesize", self._synthesize)
        g.add_node("report", self._report)
        g.add_edge(START, "screen")
        g.add_conditional_edges("screen", self._route_after_screen, {"research": "research", "score": "score"})
        g.add_edge("research", "score")
        g.add_edge("score", "synthesize")
        g.add_conditional_edges("synthesize", self._route_after_synthesis, {"report": "report", "end": END})
        g.add_edge("report", END)
        return g.compile()

    @staticmethod
    async def _progress(config: RunnableConfig, step: str) -> None:
        cb = (config.get("configurable") or {}).get("progress")
        if cb:
            await cb(step)

    # ------------------------------------------------------------------ nodes
    async def _screen(self, state: PipelineState, config: RunnableConfig) -> Dict[str, Any]:
        await self._progress(config, "Deterministic screening (sanctions, PEP, geography, behaviour, graph)")
        result = await asyncio.to_thread(self.engine.run, state["ctx"], state.get("extra_edges"))
        return {
            "engine": result, "signals": list(result.signals),
            "decision_path": ["screen:complete"], "warnings": [],
            "llm_status": llm_status_for(state.get("research", False)),
        }

    def _route_after_screen(self, state: PipelineState) -> str:
        if not state.get("research"):
            return "score"
        if state["llm_status"] != "ok":
            return "score"
        conclusive = state["engine"].decision["sanctions_confirmed"]
        return "score" if conclusive else "research"

    async def _research(self, state: PipelineState, config: RunnableConfig) -> Dict[str, Any]:
        await self._progress(config, "AI research agents")
        ctx, engine = state["ctx"], state["engine"]
        confidential = state.get("confidential", False)
        sanctions_summary = "; ".join(
            f"{m['queried_name']} ~ {m['listed_name']} ({m['level']}, {m['score']})" for m in engine.sanctions_matches[:5])
        queries = build_queries(ctx, sanctions_summary)
        cache = get_cache()

        async def one(name: str, query: str) -> AgentFinding:
            key = "agent:" + hashlib.sha256(
                f"{name}|{query}|{settings.llm.groq_model}|{settings.llm.web_search_enabled}|{confidential}".encode()
            ).hexdigest()
            cached = await cache.get(key)
            if cached:
                return AgentFinding.model_validate_json(cached)
            finding = await self.runner.run(name, query, confidential=confidential)
            if finding.usable:
                await cache.set(key, finding.model_dump_json(), CACHE_TTL)
            await self._progress(config, f"{name} agent complete")
            return finding

        names = list(queries)
        findings: List[AgentFinding] = list(await asyncio.gather(*[one(n, queries[n]) for n in names]))
        failed = [f.agent for f in findings if not f.usable]
        warnings = []
        status = "ok"
        if failed:
            status = "failed" if len(failed) == len(findings) else "partial"
            warnings.append(f"AI research incomplete ({', '.join(failed)}); result relies on deterministic evidence for those domains")
        return {"findings": findings, "llm_status": status, "warnings": warnings,
                "decision_path": [f"research:{len(findings) - len(failed)}/{len(findings)}_usable"]}

    async def _score(self, state: PipelineState, config: RunnableConfig) -> Dict[str, Any]:
        await self._progress(config, "Explainable risk scoring")
        engine = state["engine"]
        findings = state.get("findings", [])
        ai_signals = findings_to_signals(findings)
        signals = list(engine.signals) + ai_signals
        score = combine_with_ai(engine.signals, ai_signals)
        decision = decide(score, signals)
        path = ["score:complete"]
        extra_warnings: List[str] = []
        if state.get("research") and state.get("llm_status") == "no_api_key":
            extra_warnings.append("AI research requested but no LLM API key is configured; deterministic analysis only")
        if state.get("research") and LLMFactory.available() and state["engine"].decision["sanctions_confirmed"]:
            path.append("research:skipped_conclusive")
        if any(s.code.startswith("AI_SANCTIONS") for s in ai_signals):
            extra_warnings.append("AI flagged a possible sanctions link from open-web evidence - unverified; analyst must confirm")
        return {"score": score, "signals": signals, "decision": decision,
                "warnings": extra_warnings, "decision_path": path}

    async def _synthesize(self, state: PipelineState, config: RunnableConfig) -> Dict[str, Any]:
        await self._progress(config, "Analyst briefing")
        engine, score, decision = state["engine"], state["score"], state["decision"]
        fallback = deterministic_summary(engine, score, decision)
        if state.get("llm_status") not in ("ok", "partial"):
            return {"summary": fallback, "summary_source": "deterministic", "decision_path": ["synthesize:deterministic"]}
        drivers = "\n".join(f"- {c['description']} ({c['points']} pts)" for c in score.contributions[:6]) or "- none"
        typologies = "\n".join(f"- {t['name']}" for t in engine.typologies) or "- none"
        findings = "\n".join(f"- {f.agent}: {f.verdict}, score {f.risk_score}, {f.summary[:120]}"
                             for f in state.get("findings", []) if f.usable) or "- none"
        prompt = PromptTemplates.format(
            "SYNTHESIS", score=score.score, level=score.level, action=decision["recommended_action"],
            regime=engine.ctx.regime, drivers=drivers, typologies=typologies, findings=findings)
        try:
            response = await asyncio.wait_for(
                LLMFactory.get_llm().ainvoke([SystemMessage(content=PromptTemplates.SYSTEM_AML_EXPERT),
                                              HumanMessage(content=prompt)]),
                timeout=settings.llm.agent_timeout_s)
            text = strip_thinking(extract_text(response.content))
            if text:
                return {"summary": text, "summary_source": "llm", "decision_path": ["synthesize:llm"]}
        except Exception as exc:
            logger.warning("Synthesis LLM call failed: %s", type(exc).__name__)
            return {"summary": fallback, "summary_source": "deterministic", "decision_path": ["synthesize:fallback"],
                    "warnings": [f"AI briefing unavailable ({type(exc).__name__}); showing deterministic summary"]}
        return {"summary": fallback, "summary_source": "deterministic", "decision_path": ["synthesize:fallback"]}

    def _route_after_synthesis(self, state: PipelineState) -> str:
        return "report" if state["decision"]["report_required"] else "end"

    async def _report(self, state: PipelineState, config: RunnableConfig) -> Dict[str, Any]:
        await self._progress(config, "Drafting regulatory report")
        findings = [f.public() for f in state.get("findings", []) if f.usable]
        report = reporting.build_report(state["engine"], state["score"], state["decision"], state["signals"],
                                        ai_findings=findings)
        return {"report": report, "decision_path": ["report:drafted"]}

    # ------------------------------------------------------------------ API
    async def analyze(
        self, ctx: EngineInput, extra_edges: Optional[List[Edge]] = None, research: bool = True,
        confidential: bool = False, progress_callback=None,
    ) -> PipelineState:
        initial: PipelineState = {"ctx": ctx, "extra_edges": extra_edges or [], "research": research,
                                  "confidential": confidential or ctx.confidential}
        return await self.graph.ainvoke(initial, config={"configurable": {"progress": progress_callback}})


def deterministic_summary(engine: EngineResult, score: ScoreResult, decision: Dict[str, Any]) -> str:
    drivers = [c for c in score.contributions if c["code"] != "POLICY_FLOOR"][:3]
    lines = [f"ASSESSMENT: {score.level} risk ({score.score}/100); recommended action {decision['recommended_action']}."]
    if score.floor_applied:
        lines[0] += " A verified sanctions match applies a mandatory policy floor."
    if drivers:
        lines.append("KEY RED FLAGS: " + "; ".join(f"{d['description']} (+{d['points']})" for d in drivers) + ".")
    else:
        lines.append("KEY RED FLAGS: none identified.")
    steps = {"BLOCK": "Block/hold the transaction, notify the compliance officer and prepare the regulatory report.",
             "ESCALATE": "Escalate to a senior analyst and prepare the regulatory report.",
             "REVIEW": "Manual analyst review within 24 hours; request supporting documents.",
             "APPROVE": "No action required; continue standard monitoring."}[decision["recommended_action"]]
    lines.append("NEXT STEPS: " + steps)
    return "\n".join(lines)
