"""
Jurisdiction risk reference data
================================

Single source of truth for country risk (previously duplicated in three
places and drifted apart). Data lives in ``sentinelai/data/jurisdictions.json``
and can be replaced with ``SENTINEL_RISK_JURISDICTIONS_FILE``.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, FrozenSet, List, Optional

from sentinelai.core.config import settings

_DEFAULT_FILE = Path(__file__).resolve().parent.parent / "data" / "jurisdictions.json"

# Risk categories, ordered from most to least severe.
CALL_FOR_ACTION = "FATF_CALL_FOR_ACTION"
SANCTIONS_EXPOSURE = "SANCTIONS_EXPOSURE"
INCREASED_MONITORING = "FATF_INCREASED_MONITORING"
OFFSHORE_SECRECY = "OFFSHORE_SECRECY"


@dataclass(frozen=True)
class JurisdictionData:
    as_of: str
    sources: Dict[str, str]
    disclaimer: str
    call_for_action: FrozenSet[str]
    increased_monitoring: FrozenSet[str]
    sanctions_exposure: FrozenSet[str]
    offshore_secrecy: FrozenSet[str]
    alpha3: Dict[str, str]
    names: Dict[str, str]

    def normalize(self, code: Optional[str]) -> str:
        """Return an upper-case ISO-3166 alpha-2 code ('' when unknown/empty)."""
        if not code:
            return ""
        code = code.strip().upper()
        if len(code) == 3:
            return self.alpha3.get(code, code)
        return code

    def categories(self, code: Optional[str]) -> List[str]:
        """All risk categories a country belongs to (a country can be in several)."""
        c = self.normalize(code)
        out = []
        if c in self.call_for_action:
            out.append(CALL_FOR_ACTION)
        if c in self.sanctions_exposure:
            out.append(SANCTIONS_EXPOSURE)
        if c in self.increased_monitoring:
            out.append(INCREASED_MONITORING)
        if c in self.offshore_secrecy:
            out.append(OFFSHORE_SECRECY)
        return out

    def name(self, code: Optional[str]) -> str:
        c = self.normalize(code)
        return self.names.get(c, c or "Unknown")

    def as_dict(self) -> Dict[str, Any]:
        return {
            "as_of": self.as_of,
            "disclaimer": self.disclaimer,
            "sources": self.sources,
            "fatf_call_for_action": sorted(self.call_for_action),
            "fatf_increased_monitoring": sorted(self.increased_monitoring),
            "sanctions_exposure": sorted(self.sanctions_exposure),
            "offshore_secrecy": sorted(self.offshore_secrecy),
            "names": self.names,
        }


@lru_cache(maxsize=1)
def get_jurisdictions() -> JurisdictionData:
    path = Path(settings.risk.jurisdictions_file) if settings.risk.jurisdictions_file else _DEFAULT_FILE
    raw = json.loads(path.read_text(encoding="utf-8"))
    return JurisdictionData(
        as_of=raw.get("as_of", "unknown"),
        sources=raw.get("sources", {}),
        disclaimer=raw.get("disclaimer", ""),
        call_for_action=frozenset(raw.get("fatf_call_for_action", [])),
        increased_monitoring=frozenset(raw.get("fatf_increased_monitoring", [])),
        sanctions_exposure=frozenset(raw.get("sanctions_exposure", [])),
        offshore_secrecy=frozenset(raw.get("offshore_secrecy", [])),
        alpha3=raw.get("alpha3_to_alpha2", {}),
        names=raw.get("names", {}),
    )
