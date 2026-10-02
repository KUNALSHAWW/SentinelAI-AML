"""LLM research layer: guarded ReAct agents orchestrated by a LangGraph state machine."""

from __future__ import annotations

__all__ = ["AMLOrchestrator", "PromptTemplates", "AgentFinding", "parse_finding"]


def __getattr__(name: str):  # lazy: importing the package must not import langgraph/langchain
    if name == "AMLOrchestrator":
        from sentinelai.agents.orchestrator import AMLOrchestrator
        return AMLOrchestrator
    if name == "PromptTemplates":
        from sentinelai.agents.prompts import PromptTemplates
        return PromptTemplates
    if name in ("AgentFinding", "parse_finding"):
        from sentinelai.agents import findings
        return getattr(findings, name)
    raise AttributeError(name)
