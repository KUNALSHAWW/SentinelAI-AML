"""
ReAct research agents
=====================

One LangGraph ``create_react_agent`` per analysis domain. Agents reason
step-by-step, optionally use (guarded) web search, and must finish with a JSON
finding (see :mod:`findings`). They are *advisory*: their output becomes capped,
unverified signals and can never lower a deterministic score.
"""

from __future__ import annotations

import asyncio
from typing import Any, Dict, List, Optional

from langchain_core.messages import HumanMessage

from sentinelai.agents.base import LLMFactory, extract_text, strip_thinking
from sentinelai.agents.findings import AgentFinding, parse_finding
from sentinelai.agents.privacy import untrusted
from sentinelai.agents.prompts import UNTRUSTED_POLICY, json_contract
from sentinelai.agents.tools import get_search_tools
from sentinelai.core import metrics
from sentinelai.core.config import settings
from sentinelai.core.logging import get_logger
from sentinelai.engine.types import EngineInput

logger = get_logger(__name__)

_ROLES: Dict[str, Dict[str, Any]] = {
    "sanctions": {
        "task": "You are a sanctions compliance analyst. Assess whether the named parties may be subject to OFAC, EU or UN "
                "sanctions (including ownership/control and aliases). Prior deterministic list screening is provided; "
                "look for evidence it may have missed (aliases, new designations, ownership links).",
        "verdicts": ["MATCH", "POTENTIAL_MATCH", "NO_MATCH"],
    },
    "pep": {
        "task": "You are a PEP screening analyst. Determine whether the customer is, or is closely associated with, a "
                "politically exposed person (foreign/domestic/international-organisation PEP or relative/close associate).",
        "verdicts": ["PEP", "POSSIBLE_PEP", "NOT_PEP"],
    },
    "geographic": {
        "task": "You are a jurisdiction-risk analyst. Assess money-laundering risk of the countries on this payment route "
                "(FATF status, sanctions exposure, secrecy, corruption, plausible business rationale for the routing).",
        "verdicts": ["NONE", "LOW", "MEDIUM", "HIGH"],
    },
    "network": {
        "task": "You are a corporate-network analyst. Look for shell-company, nominee, circular-ownership or opaque-structure "
                "indicators among the parties.",
        "verdicts": ["NONE", "LOW", "MEDIUM", "HIGH"],
    },
    "crypto": {
        "task": "You are a virtual-asset risk analyst. Assess the transfer for mixer use, darknet exposure, privacy-coin "
                "conversion and chain-hopping, and recommend blockchain-analytics follow-up.",
        "verdicts": ["NONE", "LOW", "MEDIUM", "HIGH"],
    },
    "document": {
        "task": "You are a trade-finance analyst. Assess the documents for trade-based money-laundering indicators "
                "(over/under-invoicing, phantom shipments, misdescribed goods, inconsistencies).",
        "verdicts": ["NONE", "LOW", "MEDIUM", "HIGH"],
    },
}


def system_prompt(name: str, tools_available: bool) -> str:
    role = _ROLES[name]
    tooling = (
        "You may use the search tool; query with entity names and public facts only."
        if tools_available else
        "No web search is available (privacy policy). Reason from the supplied data and your general knowledge, and "
        "state clearly when you cannot verify something."
    )
    return f"{role['task']}\n\n{tooling}\n\n{UNTRUSTED_POLICY}\n\n{json_contract(role['verdicts'])}"


def build_queries(ctx: EngineInput, sanctions_summary: str = "") -> Dict[str, str]:
    """User-turn messages per agent. All free text is sanitised, redacted and delimited."""
    route = untrusted("Route", f"{ctx.origin_country or '?'} -> {' -> '.join(ctx.intermediate_countries + [ctx.destination_country or '?'])}")
    parties = untrusted("Parties", ", ".join(ctx.parties) or "none", max_len=600)
    queries = {
        "sanctions": f"Assess sanctions exposure.\n{parties}\n{untrusted('Customer', ctx.customer_name)}\n"
                     f"Countries: {ctx.origin_country or '?'} / {ctx.destination_country or '?'}\n"
                     f"Deterministic list screening result: {sanctions_summary or 'no list hits'}",
        "pep": f"Assess PEP status.\n{untrusted('Customer', ctx.customer_name)}\n"
               f"{untrusted('Occupation', ctx.occupation)}\nNationality: {ctx.nationality or 'unknown'}",
        "geographic": f"Assess jurisdiction risk.\n{route}\nAmount (USD): {ctx.amount_usd:,.0f}",
        "network": f"Assess corporate-network risk.\n{parties}\n{untrusted('Customer', ctx.customer_name)}\n"
                   f"Customer type: {ctx.customer_type}",
    }
    if ctx.is_crypto:
        queries["crypto"] = f"Assess the virtual-asset transfer.\n{untrusted('Details', ctx.crypto_details, max_len=800)}\nAmount (USD): {ctx.amount_usd:,.0f}"
    if ctx.documents or ctx.trade_details:
        queries["document"] = (f"Assess trade documents.\n{untrusted('Documents', '; '.join(ctx.documents) or 'none', max_len=800)}\n"
                               f"{untrusted('Trade details', ctx.trade_details, max_len=800)}\nAmount (USD): {ctx.amount_usd:,.0f}")
    return queries


class AgentRunner:
    """Builds agents lazily (per tools/no-tools variant) and runs them with budgets."""

    def __init__(self):
        self._agents: Dict[tuple, Any] = {}

    def _agent(self, name: str, confidential: bool):
        from langgraph.prebuilt import create_react_agent

        tools = get_search_tools(confidential=confidential)
        key = (name, bool(tools), confidential)
        if key not in self._agents:
            self._agents[key] = create_react_agent(
                model=LLMFactory.get_llm(), tools=tools, prompt=system_prompt(name, bool(tools)),
            )
        return self._agents[key], bool(tools)

    async def run(self, name: str, query: str, confidential: bool = False) -> AgentFinding:
        timeout = settings.llm.agent_timeout_s
        try:
            agent, _ = self._agent(name, confidential)
            result = await asyncio.wait_for(
                agent.ainvoke({"messages": [HumanMessage(content=query)]},
                              config={"recursion_limit": settings.llm.agent_recursion_limit}),
                timeout=timeout,
            )
            messages = result.get("messages", [])
            text = strip_thinking(extract_text(messages[-1].content)) if messages else ""
            finding = parse_finding(name, text)
            metrics.LLM_CALLS.labels(name, finding.parse_status).inc()
            return finding
        except asyncio.TimeoutError:
            metrics.LLM_CALLS.labels(name, "timeout").inc()
            return AgentFinding(agent=name, parse_status="timeout", summary=f"Agent exceeded {timeout}s budget")
        except Exception as exc:
            metrics.LLM_CALLS.labels(name, "error").inc()
            logger.warning("Research agent '%s' failed: %s", name, type(exc).__name__)
            return AgentFinding(agent=name, parse_status="error", summary=f"{type(exc).__name__}")
