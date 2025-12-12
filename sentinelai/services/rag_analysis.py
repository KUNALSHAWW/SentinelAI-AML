"""
SentinelAI RAG Analysis Service
===============================

High-level service combining RAG retrieval with LLM-powered analysis
for comprehensive AML transaction risk assessment.
"""

from typing import Dict, Any, Optional
from datetime import datetime
import uuid

from sentinelai.services.rag_service import RAGService, RAGContext
from sentinelai.services.llm_service import HuggingFaceLLMService, LLMAnalysisResult
from sentinelai.core.logging import get_logger
from sentinelai.core.config import settings

logger = get_logger(__name__)


class RAGAnalysisResult:
    """Complete RAG-powered analysis result"""
    
    def __init__(
        self,
        request_id: str,
        transaction: Dict[str, Any],
        customer: Dict[str, Any],
        rag_context: Optional[RAGContext],
        llm_result: LLMAnalysisResult,
        processing_time_ms: int
    ):
        self.request_id = request_id
        self.transaction = transaction
        self.customer = customer
        self.rag_context = rag_context
        self.llm_result = llm_result
        self.processing_time_ms = processing_time_ms
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API response"""
        
        # Build risk factors from flagged issues
        risk_factors = []
        for issue in self.llm_result.flagged_issues:
            severity = "HIGH" if any(kw in issue.upper() for kw in ['CRITICAL', 'SANCTION', 'BLOCK']) else "MEDIUM"
            risk_factors.append({
                "code": issue.upper().replace(" ", "_")[:30],
                "description": issue,
                "severity": severity,
                "score": 15 if severity == "HIGH" else 10,
                "category": self._categorize_issue(issue)
            })
        
        # Build alerts
        alerts = []
        if self.llm_result.risk_score >= 60:
            alerts.append({
                "type": "HIGH_RISK_TRANSACTION",
                "severity": "HIGH" if self.llm_result.risk_score >= 80 else "MEDIUM",
                "title": f"{self.llm_result.risk_level} Risk Transaction Detected",
                "description": f"Transaction flagged with risk score {self.llm_result.risk_score}/100"
            })
        
        if self.rag_context and self.rag_context.adverse_media_found:
            alerts.append({
                "type": "ADVERSE_MEDIA",
                "severity": "HIGH",
                "title": "Adverse Media Detected",
                "description": f"Negative news found for entity: {self.rag_context.entity_name}"
            })
        
        if self.rag_context and self.rag_context.sanctions_indicators:
            alerts.append({
                "type": "SANCTIONS_CONCERN",
                "severity": "CRITICAL",
                "title": "Potential Sanctions Concern",
                "description": f"Sanctions keywords detected: {', '.join(self.rag_context.sanctions_indicators)}"
            })
        
        # Build next steps based on recommendation
        next_steps = self._get_next_steps(self.llm_result.recommendation)
        
        return {
            "request_id": self.request_id,
            "processed_at": datetime.utcnow().isoformat(),
            "processing_time_ms": self.processing_time_ms,
            "risk_assessment": {
                "risk_score": self.llm_result.risk_score,
                "risk_level": self.llm_result.risk_level,
                "risk_factors": risk_factors,
                "decision_path": [
                    "entry:initial_screening",
                    "rag:entity_search" if self.rag_context else "rag:skipped",
                    "llm:analysis",
                    f"decision:{self.llm_result.recommendation.lower()}"
                ],
                "alerts_triggered": len(alerts)
            },
            "llm_analysis": {
                "summary": f"Transaction analyzed as {self.llm_result.risk_level} risk with score {self.llm_result.risk_score}/100",
                "risk_indicators": self.llm_result.flagged_issues,
                "reasoning": self.llm_result.reasoning,
                "confidence_score": self.llm_result.confidence_score,
                "recommendation": self.llm_result.recommendation,
                "model_used": "huggingface" if "llm" not in self.llm_result.raw_response.lower() else "groq"
            },
            "rag_analysis": self._format_rag_analysis() if self.rag_context else None,
            "alerts": alerts,
            "recommended_action": self.llm_result.recommendation,
            "action_required": self.llm_result.risk_score >= 30,
            "next_steps": next_steps,
            "sar_required": self.llm_result.sar_required,
            "_simulation": False,
            "_rag_enabled": self.rag_context is not None
        }
    
    def _categorize_issue(self, issue: str) -> str:
        """Categorize an issue/flag"""
        issue_lower = issue.lower()
        
        if any(kw in issue_lower for kw in ['jurisdiction', 'country', 'geographic', 'haven']):
            return "geographic"
        if any(kw in issue_lower for kw in ['sanction', 'ofac', 'sdn']):
            return "sanctions"
        if any(kw in issue_lower for kw in ['pep', 'political', 'exposed']):
            return "pep"
        if any(kw in issue_lower for kw in ['adverse', 'media', 'news']):
            return "adverse_media"
        if any(kw in issue_lower for kw in ['structur', 'amount', 'large', 'threshold']):
            return "transaction"
        if any(kw in issue_lower for kw in ['account', 'customer', 'new']):
            return "customer"
        if any(kw in issue_lower for kw in ['crypto', 'bitcoin', 'virtual']):
            return "crypto"
        
        return "general"
    
    def _get_next_steps(self, recommendation: str) -> list:
        """Get recommended next steps"""
        steps = {
            "BLOCK": [
                "Immediately block transaction execution",
                "File Suspicious Activity Report (SAR) within 30 days",
                "Escalate to AML Compliance Officer",
                "Freeze related accounts pending investigation",
                "Document all findings for regulatory review"
            ],
            "ESCALATE": [
                "Escalate to senior AML analyst for review",
                "Gather additional customer documentation",
                "Perform enhanced due diligence (EDD)",
                "Review related transaction history",
                "Consider SAR filing based on EDD findings"
            ],
            "REVIEW": [
                "Manual review by compliance team required",
                "Verify source of funds documentation",
                "Confirm business purpose of transaction",
                "Check customer KYC status is current"
            ],
            "APPROVE": [
                "Transaction may proceed with standard monitoring",
                "Log analysis results for audit trail",
                "Standard ongoing monitoring applies"
            ]
        }
        return steps.get(recommendation, ["Review case details"])
    
    def _format_rag_analysis(self) -> Dict[str, Any]:
        """Format RAG analysis for response"""
        if not self.rag_context:
            return None
        
        return {
            "entity_searched": self.rag_context.entity_name,
            "entity_type": self.rag_context.entity_type,
            "search_timestamp": self.rag_context.search_timestamp,
            "sources_analyzed": self.rag_context.results_found,
            "adverse_media_found": self.rag_context.adverse_media_found,
            "sanctions_indicators": self.rag_context.sanctions_indicators,
            "business_info": self.rag_context.business_info,
            "key_findings": self.rag_context.key_findings,
            "summary": self.rag_context.summary
        }


class RAGAnalysisService:
    """
    RAG-Powered Analysis Service
    
    Orchestrates the complete analysis workflow:
    1. Determine if RAG is needed (corporate entity check)
    2. Perform web search for entity intelligence
    3. Inject RAG context into LLM prompt
    4. Execute LLM analysis with specialized AML prompt
    5. Return structured risk assessment
    """
    
    def __init__(self):
        self.logger = get_logger("service.rag_analysis")
        self.rag_service = RAGService()
        self.llm_service = HuggingFaceLLMService()
        
        self.logger.info("RAG Analysis Service initialized")
    
    async def analyze(
        self,
        transaction: Dict[str, Any],
        customer: Dict[str, Any],
        enable_rag: bool = True,
        enable_llm: bool = True
    ) -> RAGAnalysisResult:
        """
        Perform complete RAG + LLM analysis.
        
        Args:
            transaction: Transaction details
            customer: Customer information
            enable_rag: Whether to perform RAG search
            enable_llm: Whether to use LLM analysis
        
        Returns:
            RAGAnalysisResult with complete analysis
        """
        start_time = datetime.utcnow()
        request_id = str(uuid.uuid4())
        
        self.logger.info(f"Starting RAG analysis - request_id: {request_id}")
        
        rag_context: Optional[RAGContext] = None
        
        # Step 1: Determine if RAG search is needed
        customer_name = customer.get("name", "")
        customer_type = customer.get("customer_type", "INDIVIDUAL")
        
        should_rag = enable_rag and self.rag_service.is_corporate_entity(
            customer_name, 
            customer_type
        )
        
        # Step 2: Perform RAG search if needed
        if should_rag:
            self.logger.info(f"Performing RAG search for: {customer_name}")
            try:
                rag_context = await self.rag_service.search_entity(
                    entity_name=customer_name,
                    entity_type=customer_type.upper()
                )
                self.logger.info(
                    f"RAG search completed - {rag_context.results_found} results, "
                    f"adverse media: {rag_context.adverse_media_found}"
                )
            except Exception as e:
                self.logger.error(f"RAG search failed: {str(e)}")
                # Continue without RAG context
        
        # Step 3: Perform LLM analysis
        if enable_llm:
            self.logger.info("Starting LLM analysis")
            try:
                llm_result = await self.llm_service.analyze_transaction(
                    transaction=transaction,
                    customer=customer,
                    rag_context=rag_context
                )
                self.logger.info(
                    f"LLM analysis completed - risk score: {llm_result.risk_score}"
                )
            except Exception as e:
                self.logger.error(f"LLM analysis failed: {str(e)}")
                # Fall back to rule-based
                llm_result = self.llm_service._rule_based_fallback(
                    transaction, customer, rag_context
                )
        else:
            # Rule-based only
            llm_result = self.llm_service._rule_based_fallback(
                transaction, customer, rag_context
            )
        
        # Calculate processing time
        processing_time_ms = int(
            (datetime.utcnow() - start_time).total_seconds() * 1000
        )
        
        result = RAGAnalysisResult(
            request_id=request_id,
            transaction=transaction,
            customer=customer,
            rag_context=rag_context,
            llm_result=llm_result,
            processing_time_ms=processing_time_ms
        )
        
        self.logger.info(
            f"Analysis completed - request_id: {request_id}, "
            f"risk_score: {llm_result.risk_score}, "
            f"processing_time: {processing_time_ms}ms"
        )
        
        return result
    
    async def close(self):
        """Clean up resources"""
        await self.rag_service.close()
        await self.llm_service.close()
