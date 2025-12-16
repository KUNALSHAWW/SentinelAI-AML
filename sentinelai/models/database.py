"""
SentinelAI Database Models
==========================

SQLAlchemy models for persistent storage of transactions, 
cases, alerts, and audit trails.
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from enum import Enum
import uuid

from sqlalchemy import (
    Column, String, Integer, Float, Boolean, DateTime, 
    Text, JSON, ForeignKey, Index, Enum as SQLEnum, Table
)
from sqlalchemy.orm import relationship, DeclarativeBase, Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID, JSONB, ARRAY


class Base(DeclarativeBase):
    """Base class for all models"""
    pass


# Enums
class RiskLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class CaseStatus(str, Enum):
    OPEN = "OPEN"
    UNDER_REVIEW = "UNDER_REVIEW"
    ESCALATED = "ESCALATED"
    SAR_FILED = "SAR_FILED"
    CLOSED_NO_ACTION = "CLOSED_NO_ACTION"
    CLOSED_FALSE_POSITIVE = "CLOSED_FALSE_POSITIVE"


class AlertType(str, Enum):
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


class TransactionType(str, Enum):
    WIRE_TRANSFER = "WIRE_TRANSFER"
    ACH = "ACH"
    CRYPTO = "CRYPTO"
    CASH = "CASH"
    CHECK = "CHECK"
    CARD = "CARD"
    TRADE_FINANCE = "TRADE_FINANCE"


# Association Tables
case_alerts = Table(
    "case_alerts",
    Base.metadata,
    Column("case_id", UUID(as_uuid=True), ForeignKey("cases.id"), primary_key=True),
    Column("alert_id", UUID(as_uuid=True), ForeignKey("alerts.id"), primary_key=True),
)


class Customer(Base):
    """Customer/Entity model"""
    __tablename__ = "customers"
    
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    external_id: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    
    # Basic Info
    name: Mapped[str] = mapped_column(String(500), nullable=False)
    customer_type: Mapped[str] = mapped_column(String(50))  # INDIVIDUAL, CORPORATE, FINANCIAL_INSTITUTION
    
    # Risk Profile
    risk_rating: Mapped[str] = mapped_column(SQLEnum(RiskLevel), default=RiskLevel.LOW)
    risk_score: Mapped[int] = mapped_column(Integer, default=0)
    
    # KYC Status
    kyc_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    kyc_verification_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    pep_status: Mapped[bool] = mapped_column(Boolean, default=False)
    sanctions_checked: Mapped[bool] = mapped_column(Boolean, default=False)
    last_sanctions_check: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    
    # Geographic Info
    country_of_residence: Mapped[Optional[str]] = mapped_column(String(3), nullable=True)
    nationality: Mapped[Optional[str]] = mapped_column(String(3), nullable=True)
    jurisdictions: Mapped[Optional[List[str]]] = mapped_column(ARRAY(String), nullable=True)
    
    # Account Info
    account_opened_date: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    account_status: Mapped[str] = mapped_column(String(50), default="ACTIVE")
    
    # Extra Data
    extra_data: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    transactions_as_sender = relationship("Transaction", back_populates="sender", foreign_keys="Transaction.sender_id")
    transactions_as_receiver = relationship("Transaction", back_populates="receiver", foreign_keys="Transaction.receiver_id")
    
    __table_args__ = (
        Index("ix_customers_risk_rating", "risk_rating"),
        Index("ix_customers_country", "country_of_residence"),
    )


class Transaction(Base):
    """Transaction model"""
    __tablename__ = "transactions"
    
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    external_id: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    
    # Transaction Details
    transaction_type: Mapped[str] = mapped_column(SQLEnum(TransactionType))
    amount: Mapped[float] = mapped_column(Float, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="USD")
    amount_usd: Mapped[Optional[float]] = mapped_column(Float, nullable=True)  # Normalized
    
    # Parties
    sender_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("customers.id"), nullable=True)
    receiver_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("customers.id"), nullable=True)
    sender = relationship("Customer", back_populates="transactions_as_sender", foreign_keys=[sender_id])
    receiver = relationship("Customer", back_populates="transactions_as_receiver", foreign_keys=[receiver_id])
    
    # Geographic Info
    origin_country: Mapped[Optional[str]] = mapped_column(String(3), nullable=True)
    destination_country: Mapped[Optional[str]] = mapped_column(String(3), nullable=True)
    intermediate_countries: Mapped[Optional[List[str]]] = mapped_column(ARRAY(String), nullable=True)
    
    # Crypto-specific
    is_crypto: Mapped[bool] = mapped_column(Boolean, default=False)
    crypto_details: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    
    # Risk Assessment
    risk_score: Mapped[int] = mapped_column(Integer, default=0)
    risk_level: Mapped[str] = mapped_column(SQLEnum(RiskLevel), default=RiskLevel.LOW)
    is_suspicious: Mapped[bool] = mapped_column(Boolean, default=False)
    
    # Processing Status
    processed: Mapped[bool] = mapped_column(Boolean, default=False)
    processed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    
    # Documents & Evidence
    documents: Mapped[Optional[List[str]]] = mapped_column(ARRAY(String), nullable=True)
    
    # Timestamps
    transaction_date: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    
    # Metadata
    raw_data: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    
    # Relationships
    alerts = relationship("Alert", back_populates="transaction")
    
    __table_args__ = (
        Index("ix_transactions_date", "transaction_date"),
        Index("ix_transactions_risk", "risk_level", "risk_score"),
        Index("ix_transactions_suspicious", "is_suspicious"),
    )


class Alert(Base):
    """Alert/Flag model"""
    __tablename__ = "alerts"
    
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Alert Details
    alert_type: Mapped[str] = mapped_column(SQLEnum(AlertType))
    severity: Mapped[str] = mapped_column(SQLEnum(RiskLevel))
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=True)
    
    # Source
    transaction_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("transactions.id"), nullable=True)
    transaction = relationship("Transaction", back_populates="alerts")
    
    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    acknowledged: Mapped[bool] = mapped_column(Boolean, default=False)
    acknowledged_by: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    acknowledged_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    
    # Analysis
    risk_factors: Mapped[Optional[List[str]]] = mapped_column(ARRAY(String), nullable=True)
    llm_analysis: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    confidence_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    
    # Relationships
    cases = relationship("Case", secondary=case_alerts, back_populates="alerts")
    
    __table_args__ = (
        Index("ix_alerts_type", "alert_type"),
        Index("ix_alerts_active", "is_active"),
    )


class Case(Base):
    """Investigation Case model"""
    __tablename__ = "cases"
    
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    case_number: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    
    # Case Details
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(SQLEnum(CaseStatus), default=CaseStatus.OPEN)
    priority: Mapped[str] = mapped_column(SQLEnum(RiskLevel), default=RiskLevel.MEDIUM)
    
    # Assignment
    assigned_to: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    team: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    
    # Investigation
    investigation_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    decision_path: Mapped[Optional[List[str]]] = mapped_column(ARRAY(String), nullable=True)
    evidence: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    
    # LLM Analysis
    ai_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    ai_recommendation: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    ai_risk_assessment: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    
    # SAR Details (if applicable)
    sar_filed: Mapped[bool] = mapped_column(Boolean, default=False)
    sar_reference: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    sar_filed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    
    # Deadlines
    review_deadline: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    sar_deadline: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    closed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    
    # Relationships
    alerts = relationship("Alert", secondary=case_alerts, back_populates="cases")
    comments = relationship("CaseComment", back_populates="case", cascade="all, delete-orphan")
    audit_logs = relationship("AuditLog", back_populates="case", cascade="all, delete-orphan")
    
    __table_args__ = (
        Index("ix_cases_status", "status"),
        Index("ix_cases_priority", "priority"),
        Index("ix_cases_assigned", "assigned_to"),
    )


class CaseComment(Base):
    """Case comments/notes"""
    __tablename__ = "case_comments"
    
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    case_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("cases.id"), nullable=False)
    
    author: Mapped[str] = mapped_column(String(100), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    comment_type: Mapped[str] = mapped_column(String(50), default="NOTE")  # NOTE, DECISION, ESCALATION
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    
    case = relationship("Case", back_populates="comments")


class AuditLog(Base):
    """Audit trail for compliance"""
    __tablename__ = "audit_logs"
    
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Action Details
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False)
    entity_id: Mapped[str] = mapped_column(String(100), nullable=False)
    
    # Context
    user_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    ip_address: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    user_agent: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    
    # Changes
    old_values: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    new_values: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    
    # Case Reference
    case_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("cases.id"), nullable=True)
    case = relationship("Case", back_populates="audit_logs")
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    
    __table_args__ = (
        Index("ix_audit_entity", "entity_type", "entity_id"),
        Index("ix_audit_action", "action"),
        Index("ix_audit_date", "created_at"),
    )


class SanctionsList(Base):
    """Sanctions list entries"""
    __tablename__ = "sanctions_list"
    
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Entity Info
    name: Mapped[str] = mapped_column(String(500), nullable=False)
    aliases: Mapped[Optional[List[str]]] = mapped_column(ARRAY(String), nullable=True)
    entity_type: Mapped[str] = mapped_column(String(50))  # INDIVIDUAL, ORGANIZATION, VESSEL
    
    # Sanctions Info
    list_source: Mapped[str] = mapped_column(String(100))  # OFAC, EU, UN, etc.
    list_type: Mapped[str] = mapped_column(String(100))  # SDN, CONSOLIDATED, etc.
    program: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    
    # Identifiers
    id_numbers: Mapped[Optional[Dict[str, str]]] = mapped_column(JSONB, nullable=True)
    
    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    added_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    removed_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    
    # Metadata
    raw_data: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    last_updated: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    
    __table_args__ = (
        Index("ix_sanctions_name", "name"),
        Index("ix_sanctions_source", "list_source"),
    )


class PEPList(Base):
    """Politically Exposed Persons list"""
    __tablename__ = "pep_list"
    
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Person Info
    name: Mapped[str] = mapped_column(String(500), nullable=False)
    aliases: Mapped[Optional[List[str]]] = mapped_column(ARRAY(String), nullable=True)
    nationality: Mapped[Optional[str]] = mapped_column(String(3), nullable=True)
    
    # PEP Details
    pep_type: Mapped[str] = mapped_column(String(100))  # HEAD_OF_STATE, MINISTER, etc.
    position: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    organization: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    country: Mapped[Optional[str]] = mapped_column(String(3), nullable=True)
    
    # Status
    is_current: Mapped[bool] = mapped_column(Boolean, default=True)
    start_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    end_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    
    # Risk Level
    risk_level: Mapped[str] = mapped_column(SQLEnum(RiskLevel), default=RiskLevel.HIGH)
    
    # Metadata
    source: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    raw_data: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    last_updated: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    
    __table_args__ = (
        Index("ix_pep_name", "name"),
        Index("ix_pep_country", "country"),
    )


class RuleConfiguration(Base):
    """Configurable detection rules"""
    __tablename__ = "rule_configurations"
    
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Rule Info
    rule_id: Mapped[str] = mapped_column(String(100), unique=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    category: Mapped[str] = mapped_column(String(100))  # STRUCTURING, VELOCITY, GEO, etc.
    
    # Rule Definition
    rule_type: Mapped[str] = mapped_column(String(50))  # THRESHOLD, PATTERN, ML
    parameters: Mapped[Dict[str, Any]] = mapped_column(JSONB, nullable=False)
    
    # Scoring
    base_risk_score: Mapped[int] = mapped_column(Integer, default=10)
    severity: Mapped[str] = mapped_column(SQLEnum(RiskLevel), default=RiskLevel.MEDIUM)
    
    # Status
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    
    # Metadata
    created_by: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
