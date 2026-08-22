"""
SentinelAI Agentic Orchestrator
================================

Runs the specialized ReAct agents in parallel, then synthesizes their findings
with a Chain-of-Thought coordinator and produces a deterministic risk score.
"""

from typing import Dict, Any, List, Optional
from datetime import datetime
import asyncio
import re

from sentinelai.agents.specialized import (
    AMLState,
    BehavioralAnalysisAgent,
    EnhancedDueDiligenceAgent,
    RiskScoringAgent,
    SARGenerationAgent,
)
from sentinelai.agents.react_agents import build_react_agents, run_agent
from sentinelai.core.config import settings
from sentinelai.core.logging import get_logger

logger = get_logger(__name__)


def _extract_score(text: str, default: int = 0) -> int:
    """Extract a 0-100 risk score from an agent's text answer."""
    for pattern in (r"(?:risk\s*score|score)[:\s]*(\d{1,3})", r"(\d{1,3})\s*/\s*100"):
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return min(100, max(0, int(match.group(1))))
    return default


class AMLOrchestrator:
    """Orchestrates the agentic AML analysis pipeline."""

    def __init__(self):
        self.logger = get_logger("orchestrator")

        # ReAct agents (LLM + web search), built lazily on first use
        self._react_agents: Optional[Dict[str, Any]] = None

        # Deterministic agents
        self.behavioral = BehavioralAnalysisAgent()
        self.edd = EnhancedDueDiligenceAgent()
        self.scoring = RiskScoringAgent()
        self.sar = SARGenerationAgent()

        self.logger.info("Agentic AML Orchestrator initialized")

    def _get_react_agents(self) -> Dict[str, Any]:
        """Build (or return cached) ReAct agents."""
        if self._react_agents is None:
            self._react_agents = build_react_agents()
        return self._react_agents

    # =====================
    # Query builders
    # =====================

    @staticmethod
    def _geo_query(tx: Dict[str, Any]) -> str:
        return (
            "Assess the geographic/jurisdiction money-laundering risk of this transaction.\n"
            f"Origin country: {tx.get('origin_country', 'Unknown')}\n"
            f"Destination country: {tx.get('destination_country', 'Unknown')}\n"
            f"Intermediate countries: {', '.join(tx.get('intermediate_countries', [])) or 'None'}"
        )

    @staticmethod
    def _sanctions_query(tx: Dict[str, Any]) -> str:
        return (
            "Screen these parties against OFAC, EU, and UN sanctions lists.\n"
            f"Parties: {', '.join(tx.get('parties', [])) or 'None specified'}\n"
            f"Origin country: {tx.get('origin_country', 'Unknown')}"
        )

    @staticmethod
    def _pep_query(customer: Dict[str, Any]) -> str:
        return (
            "Determine whether this customer is a Politically Exposed Person (PEP) or a close associate.\n"
            f"Customer name: {customer.get('name', 'Unknown')}\n"
            f"Nationality: {customer.get('nationality', 'Unknown')}\n"
            f"Occupation: {customer.get('occupation', 'Unknown')}"
        )

    @staticmethod
    def _crypto_query(tx: Dict[str, Any]) -> str:
        return (
            "Assess the cryptocurrency risk of this transaction (mixers, darknet, wallet age, layering).\n"
            f"Crypto details: {tx.get('crypto_details', {})}\n"
            f"Amount: {tx.get('amount', 0)}"
        )

    @staticmethod
    def _document_query(tx: Dict[str, Any]) -> str:
        return (
            "Analyze these documents for trade-based money laundering (TBML) indicators.\n"
            f"Documents: {', '.join(tx.get('documents', []))}\n"
            f"Amount: {tx.get('amount', 0)}"
        )

    @staticmethod
    def _network_query(tx: Dict[str, Any], customer: Dict[str, Any]) -> str:
        return (
            "Research these entities for shell-company, nominee, and circular-ownership indicators.\n"
            f"Parties: {', '.join(tx.get('parties', [])) or 'None specified'}\n"
            f"Customer: {customer.get('name', 'Unknown')}"
        )

    # =====================
    # Parallel agent execution
    # =====================

    async def _run_react_agents(self, state: AMLState) -> AMLState:
        """Run the applicable ReAct agents in parallel and merge their findings."""
        if not state.get("enable_llm", True):
            return state

        agents = self._get_react_agents()
        tx = state["transaction"]
        customer = state["customer"]

        queries: Dict[str, str] = {
            "geographic": self._geo_query(tx),
            "sanctions": self._sanctions_query(tx),
            "pep": self._pep_query(customer),
            "network": self._network_query(tx, customer),
        }
        if tx.get("asset_type") == "CRYPTO" or tx.get("transaction_type") == "CRYPTO":
            queries["crypto"] = self._crypto_query(tx)
        if tx.get("documents"):
            queries["document"] = self._document_query(tx)

        names = list(queries.keys())
        results = await asyncio.gather(
            *[run_agent(agents[n], queries[n]) for n in names],
            return_exceptions=True,
        )

        for name, result in zip(names, results):
            if isinstance(result, Exception):
                self.logger.warning(f"ReAct agent '{name}' failed: {result}")
                continue
            text = str(result or "")
            state["llm_analysis"][name] = {
                "analysis": text,
                "score": _extract_score(text),
            }
            state["decision_path"].append(f"{name}_agent:complete")

        return state

    # =====================
    # Main flow
    # =====================

    async def analyze(
        self,
        transaction: Dict[str, Any],
        customer: Dict[str, Any],
        config: Optional[Dict[str, Any]] = None
    ) -> AMLState:
        """Run the full agentic AML analysis on a transaction."""
        start_time = datetime.utcnow()

        state = AMLState.create_initial(transaction, customer)
        if config:
            state["enable_llm"] = config.get("enable_llm", True)

        self.logger.info(
            "Starting agentic AML analysis",
            extra={
                "amount": transaction.get("amount"),
                "origin": transaction.get("origin_country"),
                "destination": transaction.get("destination_country"),
            },
        )

        try:
            # 1. Parallel ReAct agents (research + web search)
            state["decision_path"].append("entry:initial_screening")
            state = await self._run_react_agents(state)

            # 2. Deterministic behavioral analysis (velocity/structuring)
            state = await self.behavioral.process(state)

            # 3. Chain-of-Thought synthesis
            state = await self.edd.process(state)

            # 4. Deterministic risk scoring
            state = await self.scoring.process(state)

            # 5. SAR generation if required
            if state.get("sar_required"):
                state = await self.sar.process(state)

            state["processing_time_ms"] = int(
                (datetime.utcnow() - start_time).total_seconds() * 1000
            )
            state["processing_end"] = datetime.utcnow().isoformat()

            self.logger.info(
                "Agentic AML analysis completed",
                extra={
                    "risk_score": state.get("risk_score"),
                    "risk_level": state.get("risk_level"),
                    "sar_required": state.get("sar_required"),
                    "processing_time_ms": state.get("processing_time_ms"),
                },
            )
            return state

        except Exception as e:
            self.logger.error(f"AML analysis failed: {str(e)}")
            raise

    def analyze_sync(
        self,
        transaction: Dict[str, Any],
        customer: Dict[str, Any],
        config: Optional[Dict[str, Any]] = None
    ) -> AMLState:
        """Synchronous wrapper for analyze."""
        return asyncio.run(self.analyze(transaction, customer, config))

    async def batch_analyze(
        self,
        cases: List[Dict[str, Any]],
        max_concurrent: int = 5
    ) -> List[AMLState]:
        """Analyze multiple transactions in parallel."""
        semaphore = asyncio.Semaphore(max_concurrent)

        async def analyze_with_limit(case: Dict[str, Any]) -> AMLState:
            async with semaphore:
                return await self.analyze(case["transaction"], case["customer"])

        tasks = [analyze_with_limit(case) for case in cases]
        return await asyncio.gather(*tasks, return_exceptions=True)

    def get_agent_metrics(self) -> Dict[str, Any]:
        """Get metrics from the deterministic agents."""
        return {
            "behavioral": self.behavioral.get_metrics(),
            "edd": self.edd.get_metrics(),
            "scoring": self.scoring.get_metrics(),
            "sar": self.sar.get_metrics(),
        }


# =====================
# Convenience Functions
# =====================

def create_orchestrator() -> AMLOrchestrator:
    """Factory function to create orchestrator instance."""
    return AMLOrchestrator()


async def run_analysis(
    transaction: Dict[str, Any],
    customer: Dict[str, Any]
) -> AMLState:
    """Convenience function to run a single analysis."""
    orchestrator = create_orchestrator()
    return await orchestrator.analyze(transaction, customer)


def run_analysis_sync(
    transaction: Dict[str, Any],
    customer: Dict[str, Any]
) -> AMLState:
    """Synchronous version of run_analysis."""
    return asyncio.run(run_analysis(transaction, customer))
