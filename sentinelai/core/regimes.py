"""
Regulatory regime profiles
==========================

AML thresholds and reporting duties differ by jurisdiction. Instead of
hard-coding US numbers, the engine reads a :class:`Regime` so the same
detection logic can be demonstrated under India's PMLA, the US BSA, or the EU.

Sources: FinCEN SAR rules (31 CFR 1020.320); PMLA (Maintenance of Records)
Rules 2005 / FIU-IND (CTR: cash > INR 10 lakh, filed by the 15th of the next
month; STR: within 7 working days of concluding suspicion).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, Optional

from sentinelai.core.config import settings
from sentinelai.core.time import utcnow


@dataclass(frozen=True)
class Regime:
    code: str
    name: str
    regulator: str
    currency: str                    # currency of ``cash_report_threshold``
    cash_report_threshold: float     # e.g. CTR threshold in ``currency``
    structuring_band: float          # fraction of threshold at/above which "just below" applies
    suspicious_report: str           # SAR / STR
    cash_report: str                 # CTR / "cash report"
    filing_days: Optional[int]       # None => "without delay"
    working_days: bool
    deadline_note: str
    cash_threshold_is_cash_only: bool = True

    def filing_deadline(self, start: Optional[datetime] = None) -> Optional[datetime]:
        if self.filing_days is None:
            return None
        current = start or utcnow()
        if not self.working_days:
            return current + timedelta(days=self.filing_days)
        remaining = self.filing_days
        while remaining:
            current += timedelta(days=1)
            if current.weekday() < 5:
                remaining -= 1
        return current

    def as_dict(self) -> Dict[str, object]:
        return {
            "code": self.code, "name": self.name, "regulator": self.regulator,
            "currency": self.currency, "cash_report_threshold": self.cash_report_threshold,
            "suspicious_report": self.suspicious_report, "cash_report": self.cash_report,
            "filing_days": self.filing_days, "working_days": self.working_days,
            "deadline_note": self.deadline_note,
        }


REGIMES: Dict[str, Regime] = {
    "US_BSA": Regime(
        code="US_BSA", name="United States - Bank Secrecy Act", regulator="FinCEN",
        currency="USD", cash_report_threshold=10_000, structuring_band=0.90,
        suspicious_report="SAR", cash_report="CTR", filing_days=30, working_days=False,
        deadline_note="SAR within 30 calendar days of initial detection (60 if no suspect identified).",
    ),
    "IN_PMLA": Regime(
        code="IN_PMLA", name="India - PMLA 2002", regulator="FIU-IND",
        currency="INR", cash_report_threshold=1_000_000, structuring_band=0.90,
        suspicious_report="STR", cash_report="CTR", filing_days=7, working_days=True,
        deadline_note="STR within 7 working days of concluding suspicion; CTR (cash > INR 10 lakh, incl. "
                      "connected series) by the 15th of the following month.",
    ),
    "EU_AMLD": Regime(
        code="EU_AMLD", name="European Union - AMLD/AMLR", regulator="National FIU",
        currency="EUR", cash_report_threshold=10_000, structuring_band=0.90,
        suspicious_report="STR", cash_report="Cash report", filing_days=None, working_days=False,
        deadline_note="Report to the national FIU promptly / without delay; EU cash-payment cap EUR 10,000.",
    ),
}


def get_regime(code: Optional[str] = None) -> Regime:
    code = (code or settings.risk.regime).upper()
    try:
        return REGIMES[code]
    except KeyError as exc:
        raise ValueError(f"Unknown regime '{code}'. Choose one of {sorted(REGIMES)}") from exc
