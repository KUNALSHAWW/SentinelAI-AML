"""
SentinelAI Pydantic Schemas
===========================

Request/Response schemas for API validation.
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, field_validator
from enum import Enum
import uuid


# Enums for Schemas
class RiskLevelEnum(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class CaseStatusEnum(str, Enum):
    OPEN = "OPEN"
    UNDER_REVIEW = "UNDER_REVIEW"
    ESCALATED = "ESCALATED"
    SAR_FILED = "SAR_FILED"
    CLOSED_NO_ACTION = "CLOSED_NO_ACTION"
    CLOSED_FALSE_POSITIVE = "CLOSED_FALSE_POSITIVE"


class AlertTypeEnum(str, Enum):
    STRUCTURING = "STRUCTURING"
    HIGH_RISK_JURISDICTION = "HIGH_RISK_JURISDICTION"
    SANCTIONS_HIT = "SANCTIONS_HIT"
    PEP_MATCH = "PEP_MATCH"
    UNUSUAL_ACTIVITY = "UNUSUAL_ACTIVITY"
    VELOCITY_BREACH = "VELOCITY_BREACH"
    CRYPTO_RISK = "CRYPTO_RISK"
    DOCUMENT_MISMATCH = "DOCUMENT_MISMATCH"
    NETWORK_ANOMALY = "NETWORK_ANOMALY"
    ML_DETECTED = "ML_DETECTED"


class TransactionTypeEnum(str, Enum):
    WIRE_TRANSFER = "WIRE_TRANSFER"
    ACH = "ACH"
    CRYPTO = "CRYPTO"
    CASH = "CASH"
    CHECK = "CHECK"
    CARD = "CARD"
    TRADE_FINANCE = "TRADE_FINANCE"


# =====================
# Input Schemas
# =====================

class CryptoDetails(BaseModel):
    """Cryptocurrency transaction details"""
    wallet_address: Optional[str] = None
    wallet_age_days: Optional[int] = None
    mixer_used: bool = False
    darknet_market: Optional[str] = None
    cross_chain_swaps: int = 0
    token_type: Optional[str] = None  # BTC, ETH, USDT, etc.


class TransactionHistoryItem(BaseModel):
    """Historical transaction for behavioral analysis"""
    amount: float
    currency: str = "USD"
    timestamp: datetime
    transaction_type: Optional[TransactionTypeEnum] = None
    destination_country: Optional[str] = None


class TransactionInput(BaseModel):
    """Input schema for transaction analysis"""
    
    # Required Fields
    amount: float = Field(..., gt=0, description="Transaction amount")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    
    # Currency & Type
    currency: str = Field(default="USD", max_length=3)
    transaction_type: TransactionTypeEnum = Field(default=TransactionTypeEnum.WIRE_TRANSFER)
    
    # Geographic Info
    origin_country: Optional[str] = Field(None, max_length=3)
    destination_country: Optional[str] = Field(None, max_length=3)
    intermediate_countries: List[str] = Field(default_factory=list)
    
    # Parties
    parties: List[str] = Field(default_factory=list)
    sender_account: Optional[str] = None
    receiver_account: Optional[str] = None
    
    # Documents
    documents: List[str] = Field(default_factory=list)
    
    # Crypto-specific
    asset_type: Optional[str] = None  # FIAT, CRYPTO
    crypto_details: Optional[CryptoDetails] = None
    
    # Additional Metadata
    reference_id: Optional[str] = None
    notes: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @field_validator("origin_country", "destination_country", mode="before")
    @classmethod
    def uppercase_country(cls, v):
        return v.upper() if v else v


class CustomerInput(BaseModel):
    """Input schema for customer data"""
    
    # Required Fields
    name: str = Field(..., min_length=1, max_length=500)
    customer_id: Optional[str] = None
    
    # Customer Type
    customer_type: str = Field(default="INDIVIDUAL")  # INDIVIDUAL, CORPORATE
    
    # Account Info
    account_age_days: int = Field(default=0, ge=0)
    account_opened_date: Optional[datetime] = None
    
    # Geographic
    country_of_residence: Optional[str] = Field(None, max_length=3)
    nationality: Optional[str] = Field(None, max_length=3)
    
    # Transaction History
    transaction_history: List[TransactionHistoryItem] = Field(default_factory=list)
    
    # Additional Data
    occupation: Optional[str] = None
    source_of_funds: Optional[str] = None
    expected_activity: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class AnalysisRequest(BaseModel):
    """Request schema for transaction analysis"""
    
    transaction: TransactionInput
    customer: CustomerInput
    
    # Analysis Options
    enable_llm_analysis: bool = Field(default=True)
    enable_network_analysis: bool = Field(default=True)
    priority: RiskLevelEnum = Field(default=RiskLevelEnum.MEDIUM)
    
    # Correlation
    correlation_id: Optional[str] = None
    batch_id: Optional[str] = None


class BatchAnalysisRequest(BaseModel):
    """Request schema for batch analysis"""
    
    transactions: List[AnalysisRequest] = Field(..., min_length=1, max_length=1000)
    batch_id: Optional[str] = Field(default_factory=lambda: str(uuid.uuid4()))
    priority: RiskLevelEnum = Field(default=RiskLevelEnum.MEDIUM)


# =====================
# Response Schemas
# =====================

class RiskFactor(BaseModel):
    """Individual risk factor"""
    code: str
    description: str
    severity: RiskLevelEnum
    score: int
    category: str


class LLMAnalysisResult(BaseModel):
    """LLM analysis results"""
    summary: str
    risk_indicators: List[str]
    reasoning: str
    confidence_score: float = Field(ge=0, le=1)
    recommendation: str
    additional_context: Optional[Dict[str, Any]] = None


class RiskAssessmentResult(BaseModel):
    """Risk assessment results"""
    risk_score: int = Field(ge=0, le=100)
    risk_level: RiskLevelEnum
    risk_factors: List[RiskFactor]
    decision_path: List[str]
    alerts_triggered: List[str]


class AlertResponse(BaseModel):
    """Alert response schema"""
    id: uuid.UUID
    alert_type: AlertTypeEnum
    severity: RiskLevelEnum
    title: str
    description: Optional[str]
    risk_factors: List[str]
    confidence_score: Optional[float]
    created_at: datetime
    
    class Config:
        from_attributes = True


class CaseResponse(BaseModel):
    """Case response schema"""
    id: uuid.UUID
    case_number: str
    title: str
    status: CaseStatusEnum
    priority: RiskLevelEnum
    assigned_to: Optional[str]
    ai_summary: Optional[str]
    ai_recommendation: Optional[str]
    sar_filed: bool
    review_deadline: Optional[datetime]
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class AnalysisResponse(BaseModel):
    """Response schema for transaction analysis"""
    
    # Request Info
    request_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    correlation_id: Optional[str] = None
    
    # Processing Info
    processed_at: datetime = Field(default_factory=datetime.utcnow)
    processing_time_ms: int
    
    # Risk Assessment
    risk_assessment: RiskAssessmentResult
    
    # LLM Analysis
    llm_analysis: Optional[LLMAnalysisResult] = None
    
    # Generated Entities
    case: Optional[CaseResponse] = None
    alerts: List[AlertResponse] = Field(default_factory=list)
    
    # Recommendations
    action_required: bool
    recommended_action: str
    next_steps: List[str]
    
    # Reporting
    sar_required: bool
    sar_deadline: Optional[datetime] = None


class HealthResponse(BaseModel):
    """Health check response"""
    status: str
    version: str
    environment: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    dependencies: Dict[str, str]


class ErrorResponse(BaseModel):
    """Error response schema"""
    error_code: str
    message: str
    details: Optional[Dict[str, Any]] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    request_id: Optional[str] = None


# =====================
# Case Management Schemas
# =====================

class CaseCreateRequest(BaseModel):
    """Request to create a case"""
    title: str
    description: Optional[str] = None
    priority: RiskLevelEnum = RiskLevelEnum.MEDIUM
    alert_ids: List[uuid.UUID] = Field(default_factory=list)
    assigned_to: Optional[str] = None


class CaseUpdateRequest(BaseModel):
    """Request to update a case"""
    status: Optional[CaseStatusEnum] = None
    priority: Optional[RiskLevelEnum] = None
    assigned_to: Optional[str] = None
    investigation_notes: Optional[str] = None


class CaseCommentRequest(BaseModel):
    """Request to add a case comment"""
    content: str
    comment_type: str = "NOTE"


class SARGenerationRequest(BaseModel):
    """Request to generate SAR"""
    case_id: uuid.UUID
    filer_info: Dict[str, str]
    additional_notes: Optional[str] = None


# =====================
# Dashboard/Analytics Schemas
# =====================

class DashboardMetrics(BaseModel):
    """Dashboard metrics"""
    total_transactions_24h: int
    suspicious_transactions_24h: int
    open_cases: int
    pending_review: int
    sars_filed_mtd: int
    average_risk_score: float
    high_risk_percentage: float


class RiskDistribution(BaseModel):
    """Risk distribution data"""
    low: int
    medium: int
    high: int
    critical: int


class AlertTrend(BaseModel):
    """Alert trend data"""
    date: datetime
    count: int
    by_type: Dict[str, int]
