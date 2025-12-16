"""
SentinelAI Analysis Service
===========================

High-level service for transaction analysis operations.
"""

from typing import Dict, Any, List, Optional
from datetime import datetime
import uuid

from sentinelai.agents.orchestrator import AMLOrchestrator
from sentinelai.agents.specialized import AMLState
from sentinelai.models.schemas import (
    AnalysisRequest,
    AnalysisResponse,
    RiskAssessmentResult,
    RiskFactor,
    LLMAnalysisResult,
    AlertResponse,
    CaseResponse,
    RiskLevelEnum,
    AlertTypeEnum,
)
from sentinelai.core.config import settings
from sentinelai.core.logging import get_logger

logger = get_logger(__name__)


class AnalysisService:
    """
    Service for managing transaction analysis operations.
    
    Provides a high-level interface for running analyses,
    formatting results, and managing the analysis lifecycle.
    """
    
    def __init__(self):
        self.orchestrator = AMLOrchestrator()
        self.logger = get_logger("service.analysis")
    
    async def analyze_transaction(
        self,
        request: AnalysisRequest
    ) -> AnalysisResponse:
        """
        Analyze a single transaction.
        
        Args:
            request: Analysis request containing transaction and customer data
            
        Returns:
            Formatted analysis response
        """
        start_time = datetime.utcnow()
        request_id = str(uuid.uuid4())
        
        self.logger.info(
            "Starting transaction analysis",
            extra={"request_id": request_id}
        )
        
        try:
            # Convert Pydantic models to dicts for processing
            transaction_dict = request.transaction.model_dump()
            customer_dict = request.customer.model_dump()
            
            # Handle datetime serialization
            if transaction_dict.get("timestamp"):
                if isinstance(transaction_dict["timestamp"], datetime):
                    pass  # Already datetime
                else:
                    transaction_dict["timestamp"] = datetime.fromisoformat(
                        str(transaction_dict["timestamp"]).replace("Z", "+00:00")
                    )
            
            # Process transaction history timestamps
            for tx in customer_dict.get("transaction_history", []):
                if tx.get("timestamp") and not isinstance(tx["timestamp"], datetime):
                    tx["timestamp"] = datetime.fromisoformat(
                        str(tx["timestamp"]).replace("Z", "+00:00")
                    )
            
            # Run analysis
            result = await self.orchestrator.analyze(
                transaction_dict,
                customer_dict,
                config={
                    "enable_llm": request.enable_llm_analysis,
                    "enable_network": request.enable_network_analysis,
                    "priority": request.priority.value,
                }
            )
            
            # Calculate processing time
            processing_time_ms = int(
                (datetime.utcnow() - start_time).total_seconds() * 1000
            )
            
            # Build response
            response = self._build_response(
                result,
                request_id,
                request.correlation_id,
                processing_time_ms
            )
            
            self.logger.info(
                "Transaction analysis completed",
                extra={
                    "request_id": request_id,
                    "risk_score": response.risk_assessment.risk_score,
                    "risk_level": response.risk_assessment.risk_level,
                    "processing_time_ms": processing_time_ms,
                }
            )
            
            return response
            
        except Exception as e:
            self.logger.error(
                f"Transaction analysis failed: {str(e)}",
                extra={"request_id": request_id}
            )
            raise
    
    async def batch_analyze(
        self,
        requests: List[AnalysisRequest],
        max_concurrent: int = 5
    ) -> List[AnalysisResponse]:
        """
        Analyze multiple transactions in parallel.
        
        Args:
            requests: List of analysis requests
            max_concurrent: Maximum concurrent analyses
            
        Returns:
            List of analysis responses
        """
        cases = []
        for req in requests:
            transaction_dict = req.transaction.model_dump()
            customer_dict = req.customer.model_dump()
            
            # Handle timestamp
            if transaction_dict.get("timestamp"):
                if isinstance(transaction_dict["timestamp"], str):
                    transaction_dict["timestamp"] = datetime.fromisoformat(
                        transaction_dict["timestamp"].replace("Z", "+00:00")
                    )
            
            cases.append({
                "transaction": transaction_dict,
                "customer": customer_dict,
            })
        
        results = await self.orchestrator.batch_analyze(cases, max_concurrent)
        
        responses = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                self.logger.error(f"Batch item {i} failed: {str(result)}")
                continue
            
            response = self._build_response(
                result,
                str(uuid.uuid4()),
                requests[i].correlation_id if i < len(requests) else None,
                int(result.get("processing_time_ms", 0))
            )
            responses.append(response)
        
        return responses
    
    def _build_response(
        self,
        state: AMLState,
        request_id: str,
        correlation_id: Optional[str],
        processing_time_ms: int
    ) -> AnalysisResponse:
        """Build formatted response from analysis state"""
        
        # Build risk factors
        risk_factors = []
        for rf in state.get("risk_factors", []):
            # Determine severity and category
            severity = RiskLevelEnum.MEDIUM
            category = "GENERAL"
            score = 10
            
            if any(kw in rf.upper() for kw in ["SANCTION", "DARKNET", "CRITICAL"]):
                severity = RiskLevelEnum.CRITICAL
                score = 40
            elif any(kw in rf.upper() for kw in ["HIGH_RISK", "MIXER", "PEP"]):
                severity = RiskLevelEnum.HIGH
                score = 25
            elif any(kw in rf.upper() for kw in ["TAX_HAVEN", "STRUCTURING"]):
                severity = RiskLevelEnum.MEDIUM
                score = 15
            
            if "SANCTION" in rf.upper():
                category = "SANCTIONS"
            elif "PEP" in rf.upper():
                category = "PEP"
            elif "CRYPTO" in rf.upper():
                category = "CRYPTO"
            elif "GEO" in rf.upper() or "JURISDICTION" in rf.upper():
                category = "GEOGRAPHIC"
            elif "STRUCT" in rf.upper() or "VELOCITY" in rf.upper():
                category = "BEHAVIORAL"
            elif "DOC" in rf.upper() or "TBML" in rf.upper():
                category = "DOCUMENTATION"
            
            risk_factors.append(RiskFactor(
                code=rf,
                description=rf.replace("_", " ").title(),
                severity=severity,
                score=score,
                category=category
            ))
        
        # Build risk assessment
        risk_assessment = RiskAssessmentResult(
            risk_score=state.get("risk_score", 0),
            risk_level=RiskLevelEnum(state.get("risk_level", "LOW")),
            risk_factors=risk_factors,
            decision_path=state.get("decision_path", []),
            alerts_triggered=state.get("alerts", [])
        )
        
        # Build LLM analysis result
        llm_analysis = None
        llm_data = state.get("llm_analysis", {})
        if llm_data:
            edd = llm_data.get("enhanced_due_diligence", {})
            llm_analysis = LLMAnalysisResult(
                summary=edd.get("full_analysis", "")[:500] if edd else "Analysis completed",
                risk_indicators=edd.get("risk_codes", []) if edd else [],
                reasoning=" → ".join(state.get("decision_path", [])),
                confidence_score=edd.get("confidence", 0.7) if edd else 0.7,
                recommendation=self._get_recommendation(state),
                additional_context=llm_data
            )
        
        # Build alerts
        alerts = []
        for i, alert_text in enumerate(state.get("alerts", [])):
            alert_type = AlertTypeEnum.UNUSUAL_ACTIVITY
            severity = RiskLevelEnum.MEDIUM
            
            if "SANCTION" in alert_text.upper():
                alert_type = AlertTypeEnum.SANCTIONS_HIT
                severity = RiskLevelEnum.CRITICAL
            elif "PEP" in alert_text.upper():
                alert_type = AlertTypeEnum.PEP_MATCH
                severity = RiskLevelEnum.HIGH
            elif "STRUCTUR" in alert_text.upper():
                alert_type = AlertTypeEnum.STRUCTURING
                severity = RiskLevelEnum.HIGH
            elif "VELOCITY" in alert_text.upper():
                alert_type = AlertTypeEnum.VELOCITY_BREACH
                severity = RiskLevelEnum.MEDIUM
            elif "CRYPTO" in alert_text.upper() or "MIXER" in alert_text.upper():
                alert_type = AlertTypeEnum.CRYPTO_RISK
                severity = RiskLevelEnum.HIGH
            elif "JURISDICTION" in alert_text.upper():
                alert_type = AlertTypeEnum.HIGH_RISK_JURISDICTION
                severity = RiskLevelEnum.HIGH
            elif "DOC" in alert_text.upper():
                alert_type = AlertTypeEnum.DOCUMENT_MISMATCH
                severity = RiskLevelEnum.MEDIUM
            
            alerts.append(AlertResponse(
                id=uuid.uuid4(),
                alert_type=alert_type,
                severity=severity,
                title=alert_text[:100],
                description=alert_text,
                risk_factors=[rf.code for rf in risk_factors[:3]],
                confidence_score=0.8,
                created_at=datetime.utcnow()
            ))
        
        # Build case response if SAR required
        case = None
        if state.get("sar_required") or state.get("case_id"):
            case = CaseResponse(
                id=uuid.uuid4(),
                case_number=state.get("case_id", f"CASE-{uuid.uuid4().hex[:8].upper()}"),
                title=f"Suspicious Activity - Risk Score {state.get('risk_score', 0)}",
                status="SAR_FILED" if state.get("reporting_status") == "SAR_GENERATED" else "OPEN",
                priority=RiskLevelEnum(state.get("risk_level", "MEDIUM")),
                assigned_to=None,
                ai_summary=llm_analysis.summary if llm_analysis else None,
                ai_recommendation=llm_analysis.recommendation if llm_analysis else None,
                sar_filed=state.get("reporting_status") == "SAR_GENERATED",
                review_deadline=datetime.fromisoformat(state["review_deadline"]) 
                    if state.get("review_deadline") else None,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
        
        # Determine action required
        risk_score = state.get("risk_score", 0)
        action_required = risk_score >= settings.risk.medium_risk_threshold
        
        # Build next steps
        next_steps = self._get_next_steps(state)
        
        # SAR deadline
        sar_deadline = None
        if state.get("sar_required"):
            sar_deadline = datetime.utcnow() + timedelta(days=30)
        
        from datetime import timedelta
        
        return AnalysisResponse(
            request_id=request_id,
            correlation_id=correlation_id,
            processed_at=datetime.utcnow(),
            processing_time_ms=processing_time_ms,
            risk_assessment=risk_assessment,
            llm_analysis=llm_analysis,
            case=case,
            alerts=alerts,
            action_required=action_required,
            recommended_action=self._get_recommendation(state),
            next_steps=next_steps,
            sar_required=state.get("sar_required", False),
            sar_deadline=sar_deadline
        )
    
    def _get_recommendation(self, state: AMLState) -> str:
        """Get recommended action based on state"""
        if state.get("sanction_hits"):
            return "BLOCK_AND_FILE_SAR"
        
        risk_score = state.get("risk_score", 0)
        
        if risk_score >= settings.risk.critical_risk_threshold:
            return "FILE_SAR_IMMEDIATELY"
        elif risk_score >= settings.risk.high_risk_threshold:
            return "FILE_SAR"
        elif risk_score >= settings.risk.medium_risk_threshold:
            return "ESCALATE_FOR_REVIEW"
        elif risk_score >= settings.risk.low_risk_threshold:
            return "MONITOR"
        else:
            return "CLEAR"
    
    def _get_next_steps(self, state: AMLState) -> List[str]:
        """Get next steps based on state"""
        steps = []
        
        if state.get("sanction_hits"):
            steps.extend([
                "Block transaction immediately",
                "Notify compliance officer",
                "File SAR within 30 days",
                "Preserve all related documentation",
                "Consider law enforcement referral"
            ])
        elif state.get("sar_required"):
            steps.extend([
                "Review generated SAR narrative",
                "Complete SAR filing within 30 days",
                "Document investigation findings",
                "Schedule follow-up review"
            ])
        elif state.get("pep_status"):
            steps.extend([
                "Conduct enhanced due diligence",
                "Obtain senior management approval",
                "Document source of funds",
                "Implement enhanced monitoring"
            ])
        elif state.get("risk_score", 0) >= settings.risk.medium_risk_threshold:
            steps.extend([
                "Assign to compliance analyst",
                "Review within 24 hours",
                "Request additional documentation if needed",
                "Document decision and rationale"
            ])
        else:
            steps.append("No immediate action required")
            steps.append("Continue standard monitoring")
        
        return steps
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get service metrics"""
        return self.orchestrator.get_agent_metrics()
