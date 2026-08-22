"""
SentinelAI Agent Tools
======================

Web search and research tools exposed to the ReAct agents.
"""

from typing import List

from langchain_core.tools import BaseTool
from langchain_tavily import TavilySearch
from langchain_community.tools import DuckDuckGoSearchRun

from sentinelai.core.config import settings
from sentinelai.core.logging import get_logger

logger = get_logger(__name__)


def get_search_tools() -> List[BaseTool]:
    """Build the web search tools available to agents.

    Tavily is the primary (higher-quality) search; DuckDuckGo is a
    no-key fallback. Both are exposed so agents can cross-check.
    """
    tools: List[BaseTool] = []

    tavily_key = (
        settings.llm.tavily_api_key.get_secret_value()
        if settings.llm.tavily_api_key else None
    )
    if tavily_key:
        tools.append(TavilySearch(max_results=5, tavily_api_key=tavily_key))
    else:
        logger.warning("TAVILY_API_KEY not set; Tavily search disabled")

    try:
        tools.append(DuckDuckGoSearchRun())
    except Exception as e:  # pragma: no cover - environment dependent
        logger.warning(f"DuckDuckGo search unavailable: {e}")

    return tools
