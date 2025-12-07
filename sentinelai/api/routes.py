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

# Service instances (would use dependency injection in production)
analysis_service = AnalysisService()
case_service = CaseManagementService()


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
    "/",
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
        "health": "/health"
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
        result = await analysis_service.analyze_transaction(request)
        
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
        results = await analysis_service.batch_analyze(
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
    return analysis_service.get_metrics()


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
    return await case_service.create_case(request)


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
    return await case_service.list_cases(
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
    case = await case_service.get_case(case_id)
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
    case = await case_service.update_case(case_id, request)
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
    case = await case_service.assign_case(case_id, assignee)
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
    case = await case_service.escalate_case(case_id, reason, escalated_by=api_key[:8])
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
    case = await case_service.file_sar(case_id, sar_reference, filed_by=api_key[:8])
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
        case = await case_service.close_case(
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
    comment = await case_service.add_comment(
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
    return await case_service.get_comments(case_id)


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
    case_metrics = await case_service.get_dashboard_metrics()
    
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
