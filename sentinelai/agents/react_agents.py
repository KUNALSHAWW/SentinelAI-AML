"""
SentinelAI ReAct Agents
=======================

Genuine ReAct (Reason-Act-Observe) agents for AML analysis. Each agent is an
LLM-driven agent with web-search tools that reasons step-by-step, researches
the live web, and returns a structured finding.
"""

from typing import Dict, Any, List

from langchain_core.messages import HumanMessage
from langgraph.prebuilt import create_react_agent

from sentinelai.agents.base import LLMFactory
from sentinelai.agents.tools import get_search_tools
from sentinelai.core.logging import get_logger

logger = get_logger(__name__)


# =====================
# System prompts
# =====================

_SYSTEM_PROMPTS: Dict[str, str] = {
    "sanctions": (
        "You are a sanctions compliance analyst. Screen the named parties against "
        "OFAC, EU, and UN sanctions lists. Use web search to verify any potential "
        "matches. Think step-by-step (Chain-of-Thought) and cite what you found.\n\n"
        "Return a concise finding with: (1) MATCH / POTENTIAL_MATCH / NO_MATCH, "
        "(2) the list(s) matched, (3) a confidence score 0-1, and (4) a risk score 0-100."
    ),
    "pep": (
        "You are a Politically Exposed Person (PEP) screening analyst. Determine whether "
        "the customer is a PEP or a close associate. Use web search to verify names, "
        "titles, and positions. Think step-by-step and cite sources.\n\n"
        "Return: (1) PEP / NOT_PEP, (2) category (foreign/domestic/IO/RCA), "
        "(3) confidence 0-1, and (4) a risk score 0-100."
    ),
    "geographic": (
        "You are a geographic/jurisdiction risk analyst. Assess the money-laundering "
        "risk of the origin, destination, and any intermediate countries. Use web search "
        "to check FATF grey/black lists, sanctions exposure, and tax-haven status. "
        "Think step-by-step.\n\n"
        "Return: (1) a per-country risk assessment, (2) a combined risk score 0-100, "
        "and (3) the key red flags."
    ),
    "crypto": (
        "You are a cryptocurrency risk analyst. Assess the crypto transaction for mixer "
        "usage, darknet association, wallet age, and cross-chain layering. Use web search "
        "to verify wallet/market associations. Think step-by-step.\n\n"
        "Return: (1) identified risk indicators, (2) a risk score 0-100, and "
        "(3) recommended blockchain-analytics follow-up."
    ),
    "document": (
        "You are a trade-document analyst. Examine the provided documents for trade-based "
        "money laundering (TBML) indicators: over/under-invoicing, phantom shipments, "
        "forgery, and inconsistencies. Think step-by-step.\n\n"
        "Return: (1) document legitimacy assessment, (2) red-flag codes, and "
        "(3) a risk score 0-100."
    ),
    "network": (
        "You are a network/entity analyst. Research the parties for shell-company, "
        "nominee, and circular-ownership indicators. Use web search to investigate the "
        "entities. Think step-by-step.\n\n"
        "Return: (1) network structure assessment, (2) entities of concern, and "
        "(3) a risk score 0-100."
    ),
}


def build_react_agents() -> Dict[str, Any]:
    """Build the ReAct agents, one per analysis domain."""
    llm = LLMFactory.get_llm()
    tools = get_search_tools()
    return {
        name: create_react_agent(model=llm, tools=tools, prompt=prompt)
        for name, prompt in _SYSTEM_PROMPTS.items()
    }


async def run_agent(agent: Any, query: str) -> str:
    """Run a ReAct agent and return its final text answer."""
    result = await agent.ainvoke(
        {"messages": [HumanMessage(content=query)]},
        config={"recursion_limit": 50},
    )
    messages = result.get("messages", [])
    if not messages:
        return ""
    return str(messages[-1].content)
