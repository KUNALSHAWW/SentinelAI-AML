"""
SentinelAI LangGraph Orchestrator
=================================

Main workflow orchestrator using LangGraph for intelligent,
graph-based AML detection with conditional routing.
"""

from typing import Dict, Any, Literal, List, Optional
from datetime import datetime, timedelta
import asyncio

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from sentinelai.agents.specialized import (
    AMLState,
    GeographicRiskAgent,
    BehavioralAnalysisAgent,
    CryptoRiskAgent,
    SanctionsScreeningAgent,
    PEPScreeningAgent,
    DocumentAnalysisAgent,
    EnhancedDueDiligenceAgent,
    RiskScoringAgent,
    SARGenerationAgent,
)
from sentinelai.core.config import settings
from sentinelai.core.logging import get_logger

logger = get_logger(__name__)


class AMLOrchestrator:
    """
    Main AML Detection Orchestrator
    
    Orchestrates the complete AML detection workflow using LangGraph,
    with intelligent routing based on transaction characteristics and
    risk indicators.
    """
    
    def __init__(self):
        self.logger = get_logger("orchestrator")
        
        # Initialize agents
        self.agents = {
            "geographic": GeographicRiskAgent(),
            "behavioral": BehavioralAnalysisAgent(),
            "crypto": CryptoRiskAgent(),
            "sanctions": SanctionsScreeningAgent(),
            "pep": PEPScreeningAgent(),
            "documents": DocumentAnalysisAgent(),
            "edd": EnhancedDueDiligenceAgent(),
            "scoring": RiskScoringAgent(),
            "sar": SARGenerationAgent(),
        }
        
        # Build workflow
        self.workflow = self._build_workflow()
        
        # Compile with memory for checkpointing
        self.memory = MemorySaver()
        self.app = self.workflow.compile(checkpointer=self.memory)
        
        self.logger.info("AML Orchestrator initialized")
    
    def _build_workflow(self) -> StateGraph:
        """Build the LangGraph workflow"""
        
        workflow = StateGraph(AMLState)
        
        # =====================
        # Define Nodes
        # =====================
        
        # Entry point - initial screening
        async def initial_screening(state: AMLState) -> AMLState:
            """Initial transaction screening and routing decision"""
            state["processing_steps"].append({
                "step": "initial_screening",
                "timestamp": datetime.utcnow().isoformat()
            })
            state["decision_path"].append("entry:initial_screening")
            return state
        
        # Wrap agent process methods as nodes
        async def geo_analysis(state: AMLState) -> AMLState:
            return await self.agents["geographic"].process(state)
        
        async def behavioral_analysis(state: AMLState) -> AMLState:
            return await self.agents["behavioral"].process(state)
        
        async def crypto_analysis(state: AMLState) -> AMLState:
            return await self.agents["crypto"].process(state)
        
        async def sanctions_check(state: AMLState) -> AMLState:
            return await self.agents["sanctions"].process(state)
        
        async def pep_check(state: AMLState) -> AMLState:
            return await self.agents["pep"].process(state)
        
        async def document_check(state: AMLState) -> AMLState:
            return await self.agents["documents"].process(state)
        
        async def enhanced_dd(state: AMLState) -> AMLState:
            return await self.agents["edd"].process(state)
        
        async def risk_scoring(state: AMLState) -> AMLState:
            return await self.agents["scoring"].process(state)
        
        async def sar_generation(state: AMLState) -> AMLState:
            return await self.agents["sar"].process(state)
        
        async def human_review(state: AMLState) -> AMLState:
            """Mark case for human review"""
            state["decision_path"].append("routing:human_review")
            state["reporting_status"] = "PENDING_REVIEW"
            state["review_deadline"] = (
                datetime.utcnow() + timedelta(hours=24)
            ).isoformat()
            return state
        
        async def case_cleared(state: AMLState) -> AMLState:
            """Clear the case - no suspicious activity"""
            state["decision_path"].append("routing:cleared")
            state["reporting_status"] = "CLEARED"
            return state
        
        # Add nodes to workflow
        workflow.add_node("initial_screening", initial_screening)
        workflow.add_node("geo_analysis", geo_analysis)
        workflow.add_node("behavioral_analysis", behavioral_analysis)
        workflow.add_node("crypto_analysis", crypto_analysis)
        workflow.add_node("sanctions_check", sanctions_check)
        workflow.add_node("pep_check", pep_check)
        workflow.add_node("document_check", document_check)
        workflow.add_node("enhanced_dd", enhanced_dd)
        workflow.add_node("risk_scoring", risk_scoring)
        workflow.add_node("sar_generation", sar_generation)
        workflow.add_node("human_review", human_review)
        workflow.add_node("case_cleared", case_cleared)
        
        # =====================
        # Define Routing Logic
        # =====================
        
        def route_initial(state: AMLState) -> str:
            """Route based on initial transaction characteristics"""
            tx = state["transaction"]
            customer = state["customer"]
            
            # High-priority paths
            if tx.get("asset_type") == "CRYPTO" or tx.get("transaction_type") == "CRYPTO":
                state["routing_decisions"].append("initial:CRYPTO_PATH")
                return "CRYPTO_PATH"
            
            if tx.get("amount", 0) > settings.risk.very_large_transaction_threshold:
                state["routing_decisions"].append("initial:LARGE_TRANSACTION")
                return "LARGE_TRANSACTION"
            
            if customer.get("account_age_days", 365) < settings.risk.new_account_days:
                if tx.get("amount", 0) > settings.risk.large_transaction_threshold:
                    state["routing_decisions"].append("initial:NEW_ACCOUNT_ALERT")
                    return "NEW_ACCOUNT_ALERT"
            
            state["routing_decisions"].append("initial:STANDARD_FLOW")
            return "STANDARD_FLOW"
        
        def route_after_sanctions(state: AMLState) -> str:
            """Route based on sanctions screening results"""
            if state.get("sanction_hits"):
                state["routing_decisions"].append("sanctions:HIT_FOUND")
                return "SANCTION_HIT"
            state["routing_decisions"].append("sanctions:CLEAR")
            return "NO_HIT"
        
        def route_after_pep(state: AMLState) -> str:
            """Route based on PEP screening results"""
            if state.get("pep_status"):
                state["routing_decisions"].append("pep:PEP_FOUND")
                return "PEP_FOUND"
            state["routing_decisions"].append("pep:NO_PEP")
            return "NO_PEP"
        
        def route_after_crypto(state: AMLState) -> str:
            """Route based on crypto analysis results"""
            crypto_risks = [rf for rf in state.get("risk_factors", []) 
                          if "CRYPTO" in rf or "DARKNET" in rf or "MIXER" in rf]
            if crypto_risks:
                state["routing_decisions"].append("crypto:HIGH_RISK")
                return "HIGH_RISK_CRYPTO"
            state["routing_decisions"].append("crypto:NORMAL")
            return "NORMAL_CRYPTO"
        
        def route_final_decision(state: AMLState) -> str:
            """Final routing based on risk score"""
            score = state.get("risk_score", 0)
            
            if score >= settings.risk.critical_risk_threshold:
                state["routing_decisions"].append("final:CRITICAL_SAR")
                return "FILE_SAR"
            
            if score >= settings.risk.high_risk_threshold:
                state["routing_decisions"].append("final:HIGH_RISK_SAR")
                return "FILE_SAR"
            
            if score >= settings.risk.medium_risk_threshold:
                state["routing_decisions"].append("final:MEDIUM_REVIEW")
                return "HUMAN_REVIEW"
            
            state["routing_decisions"].append("final:LOW_RISK_CLEAR")
            return "CLEAR"
        
        # =====================
        # Define Edges
        # =====================
        
        # Entry point
        workflow.set_entry_point("initial_screening")
        
        # Initial routing
        workflow.add_conditional_edges(
            "initial_screening",
            route_initial,
            {
                "CRYPTO_PATH": "crypto_analysis",
                "LARGE_TRANSACTION": "sanctions_check",
                "NEW_ACCOUNT_ALERT": "enhanced_dd",
                "STANDARD_FLOW": "geo_analysis",
            }
        )
        
        # Crypto path
        workflow.add_conditional_edges(
            "crypto_analysis",
            route_after_crypto,
            {
                "HIGH_RISK_CRYPTO": "enhanced_dd",
                "NORMAL_CRYPTO": "geo_analysis",
            }
        )
        
        # Standard flow
        workflow.add_edge("geo_analysis", "behavioral_analysis")
        workflow.add_edge("behavioral_analysis", "document_check")
        workflow.add_edge("document_check", "sanctions_check")
        
        # Sanctions routing
        workflow.add_conditional_edges(
            "sanctions_check",
            route_after_sanctions,
            {
                "SANCTION_HIT": "sar_generation",
                "NO_HIT": "pep_check",
            }
        )
        
        # PEP routing
        workflow.add_conditional_edges(
            "pep_check",
            route_after_pep,
            {
                "PEP_FOUND": "enhanced_dd",
                "NO_PEP": "risk_scoring",
            }
        )
        
        # Enhanced DD to scoring
        workflow.add_edge("enhanced_dd", "risk_scoring")
        
        # Final decision routing
        workflow.add_conditional_edges(
            "risk_scoring",
            route_final_decision,
            {
                "FILE_SAR": "sar_generation",
                "HUMAN_REVIEW": "human_review",
                "CLEAR": "case_cleared",
            }
        )
        
        # Terminal nodes
        workflow.add_edge("sar_generation", END)
        workflow.add_edge("human_review", END)
        workflow.add_edge("case_cleared", END)
        
        return workflow
    
    async def analyze(
        self,
        transaction: Dict[str, Any],
        customer: Dict[str, Any],
        config: Optional[Dict[str, Any]] = None
    ) -> AMLState:
        """
        Run complete AML analysis on a transaction.
        
        Args:
            transaction: Transaction data
            customer: Customer data
            config: Optional configuration overrides
            
        Returns:
            Final analysis state with risk assessment
        """
        start_time = datetime.utcnow()
        
        # Create initial state
        initial_state = AMLState.create_initial(transaction, customer)
        
        # Run configuration
        run_config = {
            "configurable": {
                "thread_id": f"analysis_{start_time.timestamp()}",
            }
        }
        if config:
            run_config["configurable"].update(config)
        
        self.logger.info(
            "Starting AML analysis",
            extra={
                "amount": transaction.get("amount"),
                "origin": transaction.get("origin_country"),
                "destination": transaction.get("destination_country"),
            }
        )
        
        try:
            # Run the workflow
            final_state = await self.app.ainvoke(initial_state, run_config)
            
            # Calculate processing time
            processing_time = (datetime.utcnow() - start_time).total_seconds() * 1000
            final_state["processing_time_ms"] = processing_time
            final_state["processing_end"] = datetime.utcnow().isoformat()
            
            self.logger.info(
                "AML analysis completed",
                extra={
                    "risk_score": final_state.get("risk_score"),
                    "risk_level": final_state.get("risk_level"),
                    "sar_required": final_state.get("sar_required"),
                    "processing_time_ms": processing_time,
                    "decision_path": final_state.get("decision_path"),
                }
            )
            
            return final_state
            
        except Exception as e:
            self.logger.error(f"AML analysis failed: {str(e)}")
            raise
    
    def analyze_sync(
        self,
        transaction: Dict[str, Any],
        customer: Dict[str, Any],
        config: Optional[Dict[str, Any]] = None
    ) -> AMLState:
        """Synchronous wrapper for analyze"""
        return asyncio.run(self.analyze(transaction, customer, config))
    
    async def batch_analyze(
        self,
        cases: List[Dict[str, Any]],
        max_concurrent: int = 5
    ) -> List[AMLState]:
        """
        Analyze multiple transactions in parallel.
        
        Args:
            cases: List of dicts with 'transaction' and 'customer' keys
            max_concurrent: Maximum concurrent analyses
            
        Returns:
            List of analysis results
        """
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def analyze_with_limit(case: Dict[str, Any]) -> AMLState:
            async with semaphore:
                return await self.analyze(
                    case["transaction"],
                    case["customer"]
                )
        
        tasks = [analyze_with_limit(case) for case in cases]
        return await asyncio.gather(*tasks, return_exceptions=True)
    
    def get_workflow_graph(self) -> str:
        """Get a string representation of the workflow graph"""
        return self.app.get_graph().draw_ascii()
    
    def get_agent_metrics(self) -> Dict[str, Any]:
        """Get metrics from all agents"""
        return {
            name: agent.get_metrics()
            for name, agent in self.agents.items()
        }


# =====================
# Convenience Functions
# =====================

def create_orchestrator() -> AMLOrchestrator:
    """Factory function to create orchestrator instance"""
    return AMLOrchestrator()


async def run_analysis(
    transaction: Dict[str, Any],
    customer: Dict[str, Any]
) -> AMLState:
    """
    Convenience function to run a single analysis.
    
    Args:
        transaction: Transaction data
        customer: Customer data
        
    Returns:
        Analysis result state
    """
    orchestrator = create_orchestrator()
    return await orchestrator.analyze(transaction, customer)


def run_analysis_sync(
    transaction: Dict[str, Any],
    customer: Dict[str, Any]
) -> AMLState:
    """Synchronous version of run_analysis"""
    return asyncio.run(run_analysis(transaction, customer))
