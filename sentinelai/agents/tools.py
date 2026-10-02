"""Web-search tools exposed to the ReAct agents (opt-in, guarded)."""

from __future__ import annotations

from typing import List

from sentinelai.agents.privacy import guard_tool
from sentinelai.core.config import settings
from sentinelai.core.logging import get_logger

logger = get_logger(__name__)


def get_search_tools(confidential: bool = False) -> List:
    """Guarded search tools, or ``[]`` when web search is disabled by policy."""
    if not settings.llm.web_search_enabled:
        return []
    tools: List = []
    key = settings.llm.tavily_api_key.get_secret_value() if settings.llm.tavily_api_key else None
    if key:
        try:
            from langchain_tavily import TavilySearch
            tools.append(guard_tool(TavilySearch(max_results=5, tavily_api_key=key), confidential))
        except Exception as exc:  # pragma: no cover - optional dependency
            logger.warning("Tavily unavailable: %s", exc)
    try:
        from langchain_community.tools import DuckDuckGoSearchRun
        tools.append(guard_tool(DuckDuckGoSearchRun(), confidential))
    except Exception as exc:  # pragma: no cover - optional dependency
        logger.warning("DuckDuckGo search unavailable: %s", exc)
    return tools
