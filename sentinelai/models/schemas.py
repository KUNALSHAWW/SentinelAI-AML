"""
SentinelAI Pydantic schemas
===========================

Request/response contracts for the API. Responses are a strict superset of the
original contract, adding explainability, typologies, screening evidence, the
transaction graph and honest LLM/mode reporting.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from sentinelai.core.time import utcnow


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
    UPI = "UPI"
    NEFT_RTGS = "NEFT_RTGS"


RegimeLiteral = Literal["US_BSA", "IN_PMLA", "EU_AMLD"]


# =====================
# Input
# =====================

class CryptoDetails(BaseModel):
    wallet_address: Optional[str] = None
    wallet_age_days: Optional[int] = Field(default=None, ge=0)
    mixer_used: bool = False
    mixer_service: Optional[str] = None
    darknet_market: Optional[str] = None
    cross_chain_swaps: int = Field(default=0, ge=0)
    privacy_coin: bool = False
    token_type: Optional[str] = None


class TradeDetails(BaseModel):
    """Optional trade-finance facts enabling price-deviation (TBML) checks."""
    goods_description: Optional[str] = None
    invoice_value: Optional[float] = Field(default=None, ge=0)
    market_value_estimate: Optional[float] = Field(default=None, ge=0)
    quantity: Optional[float] = Field(default=None, ge=0)
    unit_price: Optional[float] = Field(default=None, ge=0)


class TransactionHistoryItem(BaseModel):
    """Historical customer transaction. ``counterparty`` feeds the transaction graph."""
    amount: float = Field(..., ge=0)
    currency: str = Field(default="USD", max_length=8)
    timestamp: datetime
    transaction_type: Optional[TransactionTypeEnum] = None
    destination_country: Optional[str] = Field(default=None, max_length=3)
    counterparty: Optional[str] = Field(default=None, max_length=300)
    direction: Literal["IN", "OUT"] = "OUT"


class NetworkTransaction(BaseModel):
    """A flow between two other entities (from the bank's wider data) - enables multi-hop graph analysis."""
    sender: str = Field(..., max_length=300)
    receiver: str = Field(..., max_length=300)
    amount: float = Field(..., ge=0)
    currency: str = Field(default="USD", max_length=8)
    timestamp: datetime
    reference: Optional[str] = None


class TransactionInput(BaseModel):
    amount: float = Field(..., gt=0, description="Transaction amount in `currency`")
    timestamp: datetime = Field(default_factory=utcnow)
    currency: str = Field(default="USD", min_length=3, max_length=8)
    transaction_type: TransactionTypeEnum = TransactionTypeEnum.WIRE_TRANSFER
    direction: Literal["IN", "OUT"] = Field(
        default="OUT", description="OUT: the customer pays the counterparty; IN: the customer receives funds")

    origin_country: Optional[str] = Field(None, max_length=3)
    destination_country: Optional[str] = Field(None, max_length=3)
    intermediate_countries: List[str] = Field(default_factory=list, max_length=10)

    parties: List[str] = Field(default_factory=list, max_length=25)
    sender_account: Optional[str] = Field(default=None, max_length=300)
    receiver_account: Optional[str] = Field(default=None, max_length=300)

    documents: List[str] = Field(default_factory=list, max_length=25)
    trade_details: Optional[TradeDetails] = None

    asset_type: Optional[str] = None
    crypto_details: Optional[CryptoDetails] = None

    reference_id: Optional[str] = None
    notes: Optional[str] = Field(default=None, max_length=2000)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @field_validator("origin_country", "destination_country", mode="before")
    @classmethod
    def _upper_country(cls, v):
        return v.strip().upper() if isinstance(v, str) and v.strip() else None

    @field_validator("intermediate_countries", mode="before")
    @classmethod
    def _upper_countries(cls, v):
        return [c.strip().upper() for c in v if isinstance(c, str) and c.strip()] if v else []

    @field_validator("currency", mode="before")
    @classmethod
    def _upper_currency(cls, v):
        return v.strip().upper() if isinstance(v, str) else v


class CustomerInput(BaseModel):
    name: str = Field(..., min_length=1, max_length=500)
    customer_id: Optional[str] = Field(default=None, max_length=200)
    customer_type: str = Field(default="INDIVIDUAL", max_length=40)

    # None = unknown. (0 used to be the default and silently meant "brand new" or "old" depending on the endpoint.)
    account_age_days: Optional[int] = Field(default=None, ge=0)
    account_opened_date: Optional[datetime] = None

    country_of_residence: Optional[str] = Field(None, max_length=3)
    nationality: Optional[str] = Field(None, max_length=3)

    transaction_history: List[TransactionHistoryItem] = Field(default_factory=list, max_length=500)

    occupation: Optional[str] = Field(default=None, max_length=300)
    source_of_funds: Optional[str] = Field(default=None, max_length=500)
    expected_activity: Optional[str] = Field(default=None, max_length=500)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @field_validator("customer_type", mode="before")
    @classmethod
    def _upper_type(cls, v):
        return v.strip().upper() if isinstance(v, str) else v


class AnalysisRequest(BaseModel):
    transaction: TransactionInput
    customer: CustomerInput
    network_transactions: List[NetworkTransaction] = Field(default_factory=list, max_length=1000)

    enable_llm_analysis: bool = Field(default=True, description="Request AI research on top of the deterministic engine")
    enable_network_analysis: bool = Field(default=True, description="Run transaction-graph motif detection")
    restrict_external_lookup: bool = Field(
        default=False,
        description="Confidential subject (e.g. an open SAR/STR): never send to any external service, "
                    "even when web search is enabled.",
    )
    regime: Optional[RegimeLiteral] = Field(default=None, description="Override the configured regulatory regime")
    priority: RiskLevelEnum = RiskLevelEnum.MEDIUM
    persist: bool = Field(default=True, description="Persist analysis, alerts, case and graph edges")

    correlation_id: Optional[str] = None
    batch_id: Optional[str] = None


class BatchAnalysisRequest(BaseModel):
    transactions: List[AnalysisRequest] = Field(..., min_length=1, max_length=1000)
    batch_id: Optional[str] = Field(default_factory=lambda: str(uuid.uuid4()))
    priority: RiskLevelEnum = RiskLevelEnum.MEDIUM


# =====================
# Output
# =====================

class RiskFactor(BaseModel):
    code: str
    description: str
    severity: RiskLevelEnum
    score: int = Field(description="Points this factor contributes to the final score (sums to the score)")
    category: str
    typology: Optional[str] = None


class LLMAnalysisResult(BaseModel):
    summary: str
    risk_indicators: List[str]
    reasoning: str
    confidence_score: float = Field(ge=0, le=1)
    recommendation: str
    additional_context: Optional[Dict[str, Any]] = None


class RiskAssessmentResult(BaseModel):
    risk_score: int = Field(ge=0, le=100)
    risk_level: RiskLevelEnum
    risk_factors: List[RiskFactor]
    decision_path: List[str]
    alerts_triggered: List[str]


class AlertResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: uuid.UUID
    alert_type: AlertTypeEnum
    severity: RiskLevelEnum
    title: str
    description: Optional[str] = None
    risk_factors: List[str] = Field(default_factory=list, validation_alias="signal_codes")
    confidence_score: Optional[float] = None
    status: str = "OPEN"
    created_at: datetime


class CaseResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    case_number: str
    title: str
    status: CaseStatusEnum
    priority: RiskLevelEnum
    assigned_to: Optional[str] = None
    analysis_id: Optional[uuid.UUID] = None
    ai_summary: Optional[str] = None
    ai_recommendation: Optional[str] = None
    sar_filed: bool = False
    sar_reference: Optional[str] = None
    review_deadline: Optional[datetime] = None
    report_deadline: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime


class Explanation(BaseModel):
    contributions: List[Dict[str, Any]]
    category_scores: Dict[str, int]
    counterfactuals: List[Dict[str, Any]]
    floor_applied: Optional[str] = None
    method: str = "noisy-OR evidence fusion with per-category correlation discount; contributions sum to the score"
    ai_uplift_cap: int = 0


class AnalysisResponse(BaseModel):
    request_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    analysis_id: Optional[uuid.UUID] = None
    correlation_id: Optional[str] = None
    processed_at: datetime = Field(default_factory=utcnow)
    processing_time_ms: int

    # How this result was produced - never silent.
    mode: Literal["deterministic", "hybrid"] = "deterministic"
    llm_status: str = "disabled"
    warnings: List[str] = Field(default_factory=list)
    regime: Dict[str, Any] = Field(default_factory=dict)

    risk_assessment: RiskAssessmentResult
    explanation: Optional[Explanation] = None
    typologies: List[Dict[str, Any]] = Field(default_factory=list)
    screening: Dict[str, Any] = Field(default_factory=dict)
    graph: Dict[str, Any] = Field(default_factory=dict)
    ai_findings: List[Dict[str, Any]] = Field(default_factory=list)
    llm_analysis: Optional[LLMAnalysisResult] = None

    case: Optional[CaseResponse] = None
    alerts: List[AlertResponse] = Field(default_factory=list)

    action_required: bool
    recommended_action: str
    next_steps: List[str]

    sar_required: bool
    sar_deadline: Optional[datetime] = None
    report: Optional[Dict[str, Any]] = None
    audit: Optional[Dict[str, Any]] = None


class BatchItemResult(BaseModel):
    """One batch entry. Failures are reported, never silently dropped."""
    index: int
    status: Literal["ok", "error"]
    result: Optional[AnalysisResponse] = None
    error: Optional[str] = None


class BatchAnalysisResponse(BaseModel):
    batch_id: Optional[str] = None
    total: int
    succeeded: int
    failed: int
    items: List[BatchItemResult]


class HealthResponse(BaseModel):
    status: str
    version: str
    environment: str
    timestamp: datetime = Field(default_factory=utcnow)
    dependencies: Dict[str, Any]


class ErrorResponse(BaseModel):
    error_code: str
    message: str
    details: Optional[Dict[str, Any]] = None
    timestamp: datetime = Field(default_factory=utcnow)
    request_id: Optional[str] = None


# =====================
# Case management
# =====================

class CaseCreateRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=500)
    description: Optional[str] = Field(default=None, max_length=5000)
    priority: RiskLevelEnum = RiskLevelEnum.MEDIUM
    alert_ids: List[uuid.UUID] = Field(default_factory=list)
    assigned_to: Optional[str] = Field(default=None, max_length=100)
    analysis_id: Optional[uuid.UUID] = None


class CaseUpdateRequest(BaseModel):
    status: Optional[CaseStatusEnum] = None
    priority: Optional[RiskLevelEnum] = None
    assigned_to: Optional[str] = Field(default=None, max_length=100)
    investigation_notes: Optional[str] = Field(default=None, max_length=10000)
    sar_reference: Optional[str] = Field(default=None, max_length=100)


class CaseCommentRequest(BaseModel):
    content: str = Field(..., min_length=1, max_length=5000)
    comment_type: str = Field(default="NOTE", max_length=32)


class CommentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    case_id: uuid.UUID
    author: str
    content: str
    comment_type: str
    created_at: datetime


class DashboardMetrics(BaseModel):
    total_transactions_24h: int
    suspicious_transactions_24h: int
    open_cases: int
    pending_review: int
    sars_filed_mtd: int
    average_risk_score: float
    high_risk_percentage: float
    overdue_cases: int = 0
    risk_distribution: Dict[str, int] = Field(default_factory=dict)
    cases_by_status: Dict[str, int] = Field(default_factory=dict)


class AuditVerifyResponse(BaseModel):
    valid: bool
    entries: int
    head_hash: str
    first_invalid_seq: Optional[int] = None
    detail: str = ""
