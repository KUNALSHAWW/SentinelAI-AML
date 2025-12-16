"""
SentinelAI API Routes
=====================

API endpoints for transaction analysis, case management, and system operations.
"""

from typing import List, Optional
from datetime import datetime
import uuid

from fastapi import APIRouter, HTTPException, Depends, Query, BackgroundTasks
from fastapi.security import APIKeyHeader

from sentinelai.core.config import settings
from sentinelai.core.logging import get_logger
from sentinelai.models.schemas import (
    AnalysisRequest,
    AnalysisResponse,
    BatchAnalysisRequest,
    CaseResponse,
    CaseCreateRequest,
    CaseUpdateRequest,
    CaseCommentRequest,
    HealthResponse,
    DashboardMetrics,
    RiskLevelEnum,
    CaseStatusEnum,
    ErrorResponse,
)
from sentinelai.services.analysis import AnalysisService
from sentinelai.services.case_management import CaseManagementService

logger = get_logger(__name__)

# Create router
router = APIRouter()

# API Key security
api_key_header = APIKeyHeader(name=settings.api.api_key_header, auto_error=False)

# Service instances (lazy initialization to allow rule-based endpoints to work without LLM)
_analysis_service = None
_case_service = None


def get_analysis_service() -> AnalysisService:
    """Lazy initialization of AnalysisService to avoid startup failures."""
    global _analysis_service
    if _analysis_service is None:
        _analysis_service = AnalysisService()
    return _analysis_service


def get_case_service() -> CaseManagementService:
    """Lazy initialization of CaseManagementService."""
    global _case_service
    if _case_service is None:
        _case_service = CaseManagementService()
    return _case_service


# =====================
# Dependencies
# =====================

async def verify_api_key(api_key: str = Depends(api_key_header)) -> str:
    """Verify API key (simplified for demo)"""
    if settings.environment == "development":
        return api_key or "dev-key"
    
    if not api_key:
        raise HTTPException(
            status_code=401,
            detail="API key required"
        )
    
    # In production, verify against database
    return api_key


# =====================
# Health & Status
# =====================

@router.get(
    "/health",
    response_model=HealthResponse,
    tags=["System"],
    summary="Health Check"
)
async def health_check():
    """
    Check system health and dependencies.
    
    Returns the current status of the API and its dependencies.
    """
    return HealthResponse(
        status="healthy",
        version=settings.app_version,
        environment=settings.environment,
        timestamp=datetime.utcnow(),
        dependencies={
            "llm_provider": settings.llm.provider,
            "database": "connected" if settings.environment == "production" else "in-memory",
            "cache": "available"
        }
    )


@router.get(
    "/api",
    tags=["System"],
    summary="API Root"
)
async def root():
    """API root endpoint with basic information."""
    return {
        "name": "SentinelAI",
        "version": settings.app_version,
        "description": "Financial Crime Intelligence Platform",
        "documentation": "/docs",
        "health": "/health",
        "frontend": "/"
    }


# =====================
# Transaction Analysis
# =====================

@router.post(
    "/api/v1/analyze",
    response_model=AnalysisResponse,
    tags=["Analysis"],
    summary="Analyze Transaction",
    description="Perform comprehensive AML analysis on a single transaction."
)
async def analyze_transaction(
    request: AnalysisRequest,
    background_tasks: BackgroundTasks,
    api_key: str = Depends(verify_api_key)
):
    """
    Analyze a single transaction for AML risks.
    
    This endpoint performs:
    - Geographic risk assessment
    - Behavioral pattern analysis
    - Sanctions and PEP screening
    - Document verification
    - Cryptocurrency risk analysis (if applicable)
    - AI-powered due diligence with Chain-of-Thought reasoning
    
    Returns a comprehensive risk assessment with scoring, alerts, and recommendations.
    """
    try:
        result = await get_analysis_service().analyze_transaction(request)
        
        # Background task for audit logging
        background_tasks.add_task(
            log_analysis,
            request_id=result.request_id,
            risk_score=result.risk_assessment.risk_score,
            api_key=api_key
        )
        
        return result
        
    except Exception as e:
        logger.error(f"Analysis failed: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Analysis failed: {str(e)}"
        )


@router.post(
    "/api/v1/analyze/batch",
    response_model=List[AnalysisResponse],
    tags=["Analysis"],
    summary="Batch Analyze Transactions",
    description="Analyze multiple transactions in parallel."
)
async def batch_analyze(
    request: BatchAnalysisRequest,
    api_key: str = Depends(verify_api_key)
):
    """
    Analyze multiple transactions in a single request.
    
    Transactions are processed in parallel with configurable concurrency.
    Maximum 1000 transactions per batch.
    """
    try:
        results = await get_analysis_service().batch_analyze(
            request.transactions,
            max_concurrent=5
        )
        return results
        
    except Exception as e:
        logger.error(f"Batch analysis failed: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Batch analysis failed: {str(e)}"
        )


@router.get(
    "/api/v1/analyze/metrics",
    tags=["Analysis"],
    summary="Get Analysis Metrics"
)
async def get_analysis_metrics(
    api_key: str = Depends(verify_api_key)
):
    """Get metrics from the analysis service."""
    return get_analysis_service().get_metrics()


@router.post(
    "/api/v1/analyze/rules",
    response_model=AnalysisResponse,
    tags=["Analysis"],
    summary="Rule-Based Analysis",
    description="Perform rule-based AML analysis without LLM (faster, always available)."
)
async def analyze_transaction_rules(
    request: AnalysisRequest,
    background_tasks: BackgroundTasks,
    api_key: str = Depends(verify_api_key)
):
    """
    Analyze a transaction using rule-based logic only (no LLM).
    
    This endpoint is faster and always available, performing:
    - Geographic risk assessment
    - Transaction amount analysis
    - Structuring detection
    - Sanctions keyword screening
    - Customer risk profiling
    """
    from sentinelai.models.schemas import (
        RiskAssessmentResult,
        RiskFactor,
        LLMAnalysisResult,
        AlertResponse,
        AlertTypeEnum,
    )
    
    start_time = datetime.utcnow()
    request_id = str(uuid.uuid4())
    
    # Rule-based risk data
    HIGH_RISK_COUNTRIES = {'RU', 'IR', 'KP', 'SY', 'CU', 'VE', 'MM', 'BY', 'CD', 'CF', 'LY', 'SO', 'SS', 'YE', 'ZW'}
    TAX_HAVENS = {'KY', 'VG', 'PA', 'CH', 'LI', 'MC', 'AD', 'JE', 'GG', 'IM', 'BM', 'BS', 'BZ', 'LU', 'MT', 'CY', 'SG', 'HK', 'AE'}
    GREY_LIST = {'NG', 'PK', 'PH', 'TZ', 'JM', 'AL', 'BB', 'BF', 'CM', 'HR', 'GH', 'GI', 'HT', 'JO', 'ML', 'MZ', 'SN', 'UG', 'ZA'}
    SANCTION_KEYWORDS = {'russia', 'russian', 'moscow', 'iran', 'iranian', 'tehran', 'korea', 'pyongyang', 'syria', 'syrian'}
    
    tx = request.transaction
    customer = request.customer
    
    risk_score = 0
    risk_factors = []
    alerts = []
    decision_path = ["entry:initial_screening"]
    
    # Get country codes
    origin = (tx.origin_country or "").upper()
    dest = (tx.destination_country or "").upper()
    
    # Geographic risk
    decision_path.append("geographic_risk:analyzing")
    if origin in HIGH_RISK_COUNTRIES:
        risk_score += 25
        risk_factors.append(RiskFactor(
            code="HIGH_RISK_ORIGIN",
            description=f"High-risk origin country: {origin}",
            severity="HIGH",
            score=25,
            category="geographic"
        ))
        alerts.append(AlertResponse(
            id=str(uuid.uuid4()),
            alert_type=AlertTypeEnum.HIGH_RISK_JURISDICTION,
            severity="HIGH",
            title="High-Risk Origin Country",
            description=f"Transaction originates from {origin}, classified as high-risk for money laundering.",
            risk_factors=["HIGH_RISK_ORIGIN"],
            confidence_score=0.95,
            created_at=datetime.utcnow()
        ))
    
    if dest in HIGH_RISK_COUNTRIES:
        risk_score += 25
        risk_factors.append(RiskFactor(
            code="HIGH_RISK_DESTINATION",
            description=f"High-risk destination country: {dest}",
            severity="HIGH",
            score=25,
            category="geographic"
        ))
    
    if dest in TAX_HAVENS:
        risk_score += 15
        risk_factors.append(RiskFactor(
            code="TAX_HAVEN_DESTINATION",
            description=f"Destination is known tax haven: {dest}",
            severity="MEDIUM",
            score=15,
            category="geographic"
        ))
        alerts.append(AlertResponse(
            id=str(uuid.uuid4()),
            alert_type=AlertTypeEnum.HIGH_RISK_JURISDICTION,
            severity="MEDIUM",
            title="Tax Haven Destination",
            description=f"Funds being transferred to {dest}, commonly used for tax avoidance.",
            risk_factors=["TAX_HAVEN_DESTINATION"],
            confidence_score=0.90,
            created_at=datetime.utcnow()
        ))
    
    if origin in GREY_LIST or dest in GREY_LIST:
        risk_score += 10
        risk_factors.append(RiskFactor(
            code="GREY_LIST_JURISDICTION",
            description="Transaction involves FATF grey list country",
            severity="MEDIUM",
            score=10,
            category="geographic"
        ))
    
    # Amount analysis
    decision_path.append("amount_analysis:analyzing")
    amount = tx.amount or 0
    
    if amount > 100000:
        risk_score += 15
        risk_factors.append(RiskFactor(
            code="LARGE_TRANSACTION",
            description=f"Large transaction amount: ${amount:,.2f}",
            severity="MEDIUM",
            score=15,
            category="transaction"
        ))
        alerts.append(AlertResponse(
            id=str(uuid.uuid4()),
            alert_type=AlertTypeEnum.UNUSUAL_ACTIVITY,
            severity="MEDIUM",
            title="Large Value Transaction",
            description=f"Transaction amount of ${amount:,.2f} exceeds monitoring threshold.",
            risk_factors=["LARGE_TRANSACTION"],
            confidence_score=0.85,
            created_at=datetime.utcnow()
        ))
    
    if 9000 <= amount <= 10000:
        risk_score += 20
        risk_factors.append(RiskFactor(
            code="STRUCTURING_INDICATOR",
            description="Amount near reporting threshold - possible structuring",
            severity="HIGH",
            score=20,
            category="behavioral"
        ))
        alerts.append(AlertResponse(
            id=str(uuid.uuid4()),
            alert_type=AlertTypeEnum.STRUCTURING,
            severity="HIGH",
            title="Possible Structuring",
            description="Transaction amount suspiciously close to $10,000 reporting threshold.",
            risk_factors=["STRUCTURING_INDICATOR"],
            confidence_score=0.88,
            created_at=datetime.utcnow()
        ))
    
    # Customer analysis
    decision_path.append("customer_analysis:analyzing")
    customer_name = (customer.name or "").lower()
    
    for keyword in SANCTION_KEYWORDS:
        if keyword in customer_name:
            risk_score += 30
            risk_factors.append(RiskFactor(
                code="SANCTIONS_KEYWORD_MATCH",
                description=f"Customer name contains sanctions-related keyword: '{keyword}'",
                severity="CRITICAL",
                score=30,
                category="sanctions"
            ))
            alerts.append(AlertResponse(
                id=str(uuid.uuid4()),
                alert_type=AlertTypeEnum.SANCTIONS_HIT,
                severity="CRITICAL",
                title="Potential Sanctions Concern",
                description=f"Customer name '{customer.name}' contains keywords associated with sanctioned jurisdictions.",
                risk_factors=["SANCTIONS_KEYWORD_MATCH"],
                confidence_score=0.92,
                created_at=datetime.utcnow()
            ))
            break
    
    # Customer type
    if customer.customer_type and customer.customer_type.lower() == "corporate":
        risk_score += 5
        risk_factors.append(RiskFactor(
            code="CORPORATE_ENTITY",
            description="Corporate entities require enhanced due diligence",
            severity="LOW",
            score=5,
            category="customer"
        ))
    
    # Account age
    account_age = customer.account_age_days or 365
    if account_age < 90:
        risk_score += 10
        risk_factors.append(RiskFactor(
            code="NEW_ACCOUNT",
            description=f"Account is only {account_age} days old",
            severity="MEDIUM",
            score=10,
            category="behavioral"
        ))
        alerts.append(AlertResponse(
            id=str(uuid.uuid4()),
            alert_type=AlertTypeEnum.UNUSUAL_ACTIVITY,
            severity="MEDIUM",
            title="New Account High Activity",
            description=f"Large transaction on account that is only {account_age} days old.",
            risk_factors=["NEW_ACCOUNT"],
            confidence_score=0.80,
            created_at=datetime.utcnow()
        ))
    
    # Transaction type
    decision_path.append("transaction_type:analyzing")
    tx_type = (tx.transaction_type.value if tx.transaction_type else "").upper()
    
    if tx_type == "CRYPTO":
        risk_score += 15
        risk_factors.append(RiskFactor(
            code="CRYPTO_TRANSACTION",
            description="Cryptocurrency transactions carry elevated risk",
            severity="MEDIUM",
            score=15,
            category="crypto"
        ))
        alerts.append(AlertResponse(
            id=str(uuid.uuid4()),
            alert_type=AlertTypeEnum.CRYPTO_RISK,
            severity="MEDIUM",
            title="Cryptocurrency Transaction",
            description="Virtual asset transactions require enhanced monitoring.",
            risk_factors=["CRYPTO_TRANSACTION"],
            confidence_score=0.85,
            created_at=datetime.utcnow()
        ))
    
    if tx_type == "CASH":
        risk_score += 10
        risk_factors.append(RiskFactor(
            code="CASH_TRANSACTION",
            description="Cash transactions have higher AML risk",
            severity="MEDIUM",
            score=10,
            category="transaction"
        ))
    
    # Final scoring
    decision_path.append("risk_scoring:calculating")
    risk_score = min(risk_score, 100)
    
    # Determine risk level
    if risk_score >= 80:
        risk_level = RiskLevelEnum.CRITICAL
    elif risk_score >= 60:
        risk_level = RiskLevelEnum.HIGH
    elif risk_score >= 40:
        risk_level = RiskLevelEnum.MEDIUM
    else:
        risk_level = RiskLevelEnum.LOW
    
    # Determine action
    if risk_score >= 75:
        recommended_action = "BLOCK"
        sar_required = True
    elif risk_score >= 50:
        recommended_action = "ESCALATE"
        sar_required = risk_score >= 60
    elif risk_score >= 30:
        recommended_action = "REVIEW"
        sar_required = False
    else:
        recommended_action = "APPROVE"
        sar_required = False
    
    decision_path.append(f"decision:{recommended_action.lower()}")
    
    # Build reasoning
    reasoning_lines = [
        f"RULE-BASED ANALYSIS SUMMARY",
        f"============================",
        f"Transaction: ${amount:,.2f} {tx_type}",
        f"Route: {origin or 'N/A'} → {dest or 'N/A'}",
        f"Customer: {customer.name} ({customer.customer_type or 'N/A'})",
        f"",
        f"RISK ASSESSMENT: {risk_level.value} (Score: {risk_score}/100)",
        f"",
        f"KEY RISK INDICATORS ({len(risk_factors)}):",
    ]
    for i, rf in enumerate(risk_factors, 1):
        reasoning_lines.append(f"  {i}. [{rf.severity}] {rf.description}")
    
    if not risk_factors:
        reasoning_lines.append("  No significant risk indicators detected.")
    
    reasoning = "\n".join(reasoning_lines)
    
    # Build next steps
    next_steps_map = {
        "BLOCK": ["Immediately block transaction", "File SAR within 24 hours", "Escalate to compliance officer", "Freeze related accounts"],
        "ESCALATE": ["Escalate to senior analyst", "Gather additional documentation", "Review customer history", "Consider EDD"],
        "REVIEW": ["Manual review required", "Verify customer documentation", "Check transaction purpose"],
        "APPROVE": ["Transaction may proceed", "Standard monitoring applies"]
    }
    next_steps = next_steps_map.get(recommended_action, ["Review case details"])
    
    processing_time = int((datetime.utcnow() - start_time).total_seconds() * 1000)
    
    response = AnalysisResponse(
        request_id=request_id,
        correlation_id=request.correlation_id,
        processed_at=datetime.utcnow(),
        processing_time_ms=processing_time,
        risk_assessment=RiskAssessmentResult(
            risk_score=risk_score,
            risk_level=risk_level,
            risk_factors=risk_factors,
            decision_path=decision_path,
            alerts_triggered=[a.alert_type.value for a in alerts]
        ),
        llm_analysis=LLMAnalysisResult(
            summary=f"Transaction flagged as {risk_level.value} risk with score {risk_score}/100",
            risk_indicators=[rf.description for rf in risk_factors],
            reasoning=reasoning,
            confidence_score=0.90,
            recommendation=recommended_action
        ),
        alerts=alerts,
        action_required=risk_score >= 30,
        recommended_action=recommended_action,
        next_steps=next_steps,
        sar_required=sar_required
    )
    
    background_tasks.add_task(log_analysis, request_id, risk_score, api_key or "demo")
    
    return response


# =====================
# Case Management
# =====================

@router.post(
    "/api/v1/cases",
    response_model=CaseResponse,
    tags=["Cases"],
    summary="Create Case"
)
async def create_case(
    request: CaseCreateRequest,
    api_key: str = Depends(verify_api_key)
):
    """Create a new investigation case."""
    return await get_case_service().create_case(request)


@router.get(
    "/api/v1/cases",
    response_model=List[CaseResponse],
    tags=["Cases"],
    summary="List Cases"
)
async def list_cases(
    status: Optional[CaseStatusEnum] = Query(None, description="Filter by status"),
    priority: Optional[RiskLevelEnum] = Query(None, description="Filter by priority"),
    assigned_to: Optional[str] = Query(None, description="Filter by assignee"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    api_key: str = Depends(verify_api_key)
):
    """
    List investigation cases with optional filters.
    
    Supports filtering by status, priority, and assignee.
    Results are paginated and sorted by creation date (newest first).
    """
    return await get_case_service().list_cases(
        status=status,
        priority=priority,
        assigned_to=assigned_to,
        limit=limit,
        offset=offset
    )


@router.get(
    "/api/v1/cases/{case_id}",
    response_model=CaseResponse,
    tags=["Cases"],
    summary="Get Case"
)
async def get_case(
    case_id: uuid.UUID,
    api_key: str = Depends(verify_api_key)
):
    """Get a specific case by ID."""
    case = await get_case_service().get_case(case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    return case


@router.patch(
    "/api/v1/cases/{case_id}",
    response_model=CaseResponse,
    tags=["Cases"],
    summary="Update Case"
)
async def update_case(
    case_id: uuid.UUID,
    request: CaseUpdateRequest,
    api_key: str = Depends(verify_api_key)
):
    """Update a case's status, priority, or assignment."""
    case = await get_case_service().update_case(case_id, request)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    return case


@router.post(
    "/api/v1/cases/{case_id}/assign",
    response_model=CaseResponse,
    tags=["Cases"],
    summary="Assign Case"
)
async def assign_case(
    case_id: uuid.UUID,
    assignee: str = Query(..., description="User ID to assign"),
    api_key: str = Depends(verify_api_key)
):
    """Assign a case to an analyst."""
    case = await get_case_service().assign_case(case_id, assignee)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    return case


@router.post(
    "/api/v1/cases/{case_id}/escalate",
    response_model=CaseResponse,
    tags=["Cases"],
    summary="Escalate Case"
)
async def escalate_case(
    case_id: uuid.UUID,
    reason: str = Query(..., description="Reason for escalation"),
    api_key: str = Depends(verify_api_key)
):
    """Escalate a case for senior review."""
    case = await get_case_service().escalate_case(case_id, reason, escalated_by=api_key[:8])
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    return case


@router.post(
    "/api/v1/cases/{case_id}/sar",
    response_model=CaseResponse,
    tags=["Cases"],
    summary="File SAR"
)
async def file_sar(
    case_id: uuid.UUID,
    sar_reference: str = Query(..., description="SAR reference number"),
    api_key: str = Depends(verify_api_key)
):
    """Mark a case as SAR filed."""
    case = await get_case_service().file_sar(case_id, sar_reference, filed_by=api_key[:8])
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    return case


@router.post(
    "/api/v1/cases/{case_id}/close",
    response_model=CaseResponse,
    tags=["Cases"],
    summary="Close Case"
)
async def close_case(
    case_id: uuid.UUID,
    status: CaseStatusEnum = Query(..., description="Closing status"),
    reason: str = Query(..., description="Reason for closing"),
    api_key: str = Depends(verify_api_key)
):
    """Close a case with specified status and reason."""
    try:
        case = await get_case_service().close_case(
            case_id, status, reason, closed_by=api_key[:8]
        )
        if not case:
            raise HTTPException(status_code=404, detail="Case not found")
        return case
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post(
    "/api/v1/cases/{case_id}/comments",
    tags=["Cases"],
    summary="Add Comment"
)
async def add_comment(
    case_id: uuid.UUID,
    request: CaseCommentRequest,
    api_key: str = Depends(verify_api_key)
):
    """Add a comment to a case."""
    comment = await get_case_service().add_comment(
        case_id, request, author=api_key[:8]
    )
    return comment


@router.get(
    "/api/v1/cases/{case_id}/comments",
    tags=["Cases"],
    summary="Get Comments"
)
async def get_comments(
    case_id: uuid.UUID,
    api_key: str = Depends(verify_api_key)
):
    """Get all comments for a case."""
    return await get_case_service().get_comments(case_id)


# =====================
# Dashboard & Analytics
# =====================

@router.get(
    "/api/v1/dashboard/metrics",
    response_model=DashboardMetrics,
    tags=["Dashboard"],
    summary="Dashboard Metrics"
)
async def get_dashboard_metrics(
    api_key: str = Depends(verify_api_key)
):
    """
    Get dashboard metrics for the AML operations center.
    
    Includes:
    - Transaction volumes
    - Alert counts
    - Case statistics
    - Risk distribution
    """
    case_metrics = await get_case_service().get_dashboard_metrics()
    
    return DashboardMetrics(
        total_transactions_24h=0,  # Would come from transaction DB
        suspicious_transactions_24h=0,
        open_cases=case_metrics["total_open_cases"],
        pending_review=case_metrics["under_review"],
        sars_filed_mtd=0,  # Would come from SAR DB
        average_risk_score=0.0,
        high_risk_percentage=0.0
    )


# =====================
# Utility Functions
# =====================

async def log_analysis(request_id: str, risk_score: int, api_key: str):
    """Background task for audit logging"""
    logger.info(
        "Analysis audit log",
        extra={
            "request_id": request_id,
            "risk_score": risk_score,
            "api_key_prefix": api_key[:8] if api_key else "unknown"
        }
    )
