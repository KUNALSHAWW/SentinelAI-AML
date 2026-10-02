"""
SentinelAI database models
==========================

Portable SQLAlchemy 2.0 models (SQLite for zero-config dev, PostgreSQL in
production - no dialect-specific column types). Enumerations are stored as
strings and validated in Python, so adding a status never needs a DB enum
migration.

Tables
------
analyses      one row per analysis, with the full explainable response
alerts        alerts raised by an analysis, triageable by analysts
cases         investigation cases (state machine enforced in the service layer)
case_comments analyst notes and system events
audit_log     tamper-evident, hash-chained trail of every state change
graph_edges   persisted money-flow edges - the graph accumulates across analyses
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    TypeDecorator,
    Uuid,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from sentinelai.core.time import utcnow


class UTCDateTime(TypeDecorator):
    """Stores UTC; always returns timezone-aware datetimes (SQLite drops tzinfo)."""

    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


class Base(DeclarativeBase):
    pass


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


class AlertStatus(str, Enum):
    OPEN = "OPEN"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    FALSE_POSITIVE = "FALSE_POSITIVE"
    ESCALATED = "ESCALATED"


class TransactionType(str, Enum):
    WIRE_TRANSFER = "WIRE_TRANSFER"
    ACH = "ACH"
    CRYPTO = "CRYPTO"
    CASH = "CASH"
    CHECK = "CHECK"
    CARD = "CARD"
    TRADE_FINANCE = "TRADE_FINANCE"
    UPI = "UPI"
    NEFT_RTGS = "NEFT_RTGS"


class Analysis(Base):
    __tablename__ = "analyses"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, index=True)
    request_hash: Mapped[str] = mapped_column(String(64), index=True)
    customer_id: Mapped[str] = mapped_column(String(200), index=True)
    customer_name: Mapped[str] = mapped_column(String(500))
    amount: Mapped[float] = mapped_column(Float)
    currency: Mapped[str] = mapped_column(String(8))
    amount_usd: Mapped[float] = mapped_column(Float)
    transaction_type: Mapped[str] = mapped_column(String(32))
    origin_country: Mapped[Optional[str]] = mapped_column(String(3), nullable=True)
    destination_country: Mapped[Optional[str]] = mapped_column(String(3), nullable=True)
    regime: Mapped[str] = mapped_column(String(16))
    mode: Mapped[str] = mapped_column(String(16))
    risk_score: Mapped[int] = mapped_column(Integer, index=True)
    risk_level: Mapped[str] = mapped_column(String(16), index=True)
    recommended_action: Mapped[str] = mapped_column(String(32))
    report_required: Mapped[bool] = mapped_column(Boolean, default=False)
    response: Mapped[Dict[str, Any]] = mapped_column(JSON)

    alerts: Mapped[List["Alert"]] = relationship(back_populates="analysis", cascade="all, delete-orphan")

    __table_args__ = (Index("ix_analyses_level_score", "risk_level", "risk_score"),)


class Case(Base):
    __tablename__ = "cases"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    case_number: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(500))
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default=CaseStatus.OPEN.value, index=True)
    priority: Mapped[str] = mapped_column(String(16), default=RiskLevel.MEDIUM.value, index=True)
    assigned_to: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    analysis_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid, ForeignKey("analyses.id"), nullable=True)
    investigation_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    ai_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    ai_recommendation: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    report: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    sar_filed: Mapped[bool] = mapped_column(Boolean, default=False)
    sar_reference: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    sar_filed_at: Mapped[Optional[datetime]] = mapped_column(UTCDateTime, nullable=True)
    review_deadline: Mapped[Optional[datetime]] = mapped_column(UTCDateTime, nullable=True)
    report_deadline: Mapped[Optional[datetime]] = mapped_column(UTCDateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, onupdate=utcnow)
    closed_at: Mapped[Optional[datetime]] = mapped_column(UTCDateTime, nullable=True)

    alerts: Mapped[List["Alert"]] = relationship(back_populates="case")
    comments: Mapped[List["CaseComment"]] = relationship(
        back_populates="case", cascade="all, delete-orphan", order_by="CaseComment.created_at"
    )


class Alert(Base):
    __tablename__ = "alerts"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    analysis_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid, ForeignKey("analyses.id"), nullable=True, index=True)
    case_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid, ForeignKey("cases.id"), nullable=True, index=True)
    alert_type: Mapped[str] = mapped_column(String(40), index=True)
    severity: Mapped[str] = mapped_column(String(16))
    title: Mapped[str] = mapped_column(String(500))
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    signal_codes: Mapped[List[str]] = mapped_column(JSON, default=list)
    confidence_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    status: Mapped[str] = mapped_column(String(24), default=AlertStatus.OPEN.value, index=True)
    acknowledged_by: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    acknowledged_at: Mapped[Optional[datetime]] = mapped_column(UTCDateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)

    analysis: Mapped[Optional[Analysis]] = relationship(back_populates="alerts")
    case: Mapped[Optional[Case]] = relationship(back_populates="alerts")


class CaseComment(Base):
    __tablename__ = "case_comments"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    case_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("cases.id"), index=True)
    author: Mapped[str] = mapped_column(String(100))
    content: Mapped[str] = mapped_column(Text)
    comment_type: Mapped[str] = mapped_column(String(32), default="NOTE")
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)

    case: Mapped[Case] = relationship(back_populates="comments")


class AuditLog(Base):
    """Append-only, hash-chained audit trail (see services.audit)."""

    __tablename__ = "audit_log"

    seq: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    timestamp: Mapped[str] = mapped_column(String(40))          # ISO-8601 text: hashed verbatim
    actor: Mapped[str] = mapped_column(String(100))
    action: Mapped[str] = mapped_column(String(100), index=True)
    entity_type: Mapped[str] = mapped_column(String(50))
    entity_id: Mapped[str] = mapped_column(String(100))
    payload: Mapped[str] = mapped_column(Text)                  # canonical JSON text: hashed verbatim
    prev_hash: Mapped[str] = mapped_column(String(64))
    hash: Mapped[str] = mapped_column(String(64), unique=True)

    __table_args__ = (Index("ix_audit_entity", "entity_type", "entity_id"),)


class GraphEdge(Base):
    __tablename__ = "graph_edges"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source: Mapped[str] = mapped_column(String(300), index=True)
    target: Mapped[str] = mapped_column(String(300), index=True)
    amount_usd: Mapped[float] = mapped_column(Float)
    timestamp: Mapped[datetime] = mapped_column(UTCDateTime, index=True)
    analysis_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid, nullable=True)
    ref: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    edge_key: Mapped[str] = mapped_column(String(400), unique=True)
