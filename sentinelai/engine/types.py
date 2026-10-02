"""Shared engine types."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

# Signal categories (also the keys of the explainability waterfall)
SANCTIONS = "SANCTIONS"
PEP = "PEP"
GEOGRAPHIC = "GEOGRAPHIC"
BEHAVIORAL = "BEHAVIORAL"
NETWORK = "NETWORK"
CRYPTO = "CRYPTO"
TRADE = "TRADE"
CUSTOMER = "CUSTOMER"
INTEGRITY = "INTEGRITY"
AI_RESEARCH = "AI_RESEARCH"

LEVELS = ("LOW", "MEDIUM", "HIGH", "CRITICAL")


@dataclass
class Signal:
    """One piece of evidence.

    ``weight`` is the probability-like strength of the evidence on its own
    (0 < weight < 1). Signals are fused with a noisy-OR in :mod:`scoring`, so
    the final score is monotone in evidence and decomposes exactly.
    """

    code: str
    category: str
    weight: float
    description: str
    evidence: Dict[str, Any] = field(default_factory=dict)
    typology: Optional[str] = None      # key into engine.typologies.TYPOLOGIES
    alert_type: Optional[str] = None    # AlertType enum value
    floor: Optional[int] = None         # hard minimum score this signal enforces
    subject: str = ""                   # dedupe key within a code (e.g. the party name)
    verified: bool = True               # False for unverified (e.g. web) evidence

    @property
    def severity(self) -> str:
        if self.weight >= 0.65 or (self.floor or 0) >= 90:
            return "CRITICAL"
        if self.weight >= 0.40:
            return "HIGH"
        if self.weight >= 0.18:
            return "MEDIUM"
        return "LOW"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "code": self.code,
            "category": self.category,
            "severity": self.severity,
            "weight": round(self.weight, 3),
            "description": self.description,
            "evidence": self.evidence,
            "typology": self.typology,
            "verified": self.verified,
        }


@dataclass
class HistoryTx:
    amount: float
    timestamp: datetime
    currency: str = "USD"
    counterparty: Optional[str] = None
    direction: str = "OUT"              # OUT = customer pays, IN = customer receives
    country: Optional[str] = None
    transaction_type: Optional[str] = None

    @property
    def amount_usd(self) -> float:
        from sentinelai.core.fx import to_usd
        return to_usd(self.amount, self.currency)


@dataclass
class Edge:
    """Directed money flow between two entities."""

    source: str
    target: str
    amount_usd: float
    timestamp: datetime
    ref: Optional[str] = None

    def key(self) -> str:
        return f"{self.source}->{self.target}@{self.timestamp.isoformat()}#{round(self.amount_usd, 2)}"


@dataclass
class EngineInput:
    """Normalised, validated view of a transaction + customer."""

    amount: float
    currency: str
    amount_usd: float
    transaction_type: str
    timestamp: datetime
    origin_country: str
    destination_country: str
    intermediate_countries: List[str]
    parties: List[str]
    documents: List[str]
    sender: str
    receiver: str
    crypto_details: Dict[str, Any]
    trade_details: Dict[str, Any]
    is_crypto: bool

    customer_name: str
    customer_id: str
    customer_type: str
    account_age_days: Optional[int]   # None = unknown (NOT 'brand new')
    nationality: str
    residence: str
    occupation: str
    history: List[HistoryTx]
    network_edges: List[Edge]

    regime: str
    confidential: bool = False
    enable_graph: bool = True
    notes: str = ""
    free_text: List[str] = field(default_factory=list)   # every untrusted string, for injection screening
