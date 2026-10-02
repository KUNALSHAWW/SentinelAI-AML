"""Geographic / jurisdiction risk signals."""

from __future__ import annotations

from typing import List

from sentinelai.core.jurisdictions import (
    CALL_FOR_ACTION, INCREASED_MONITORING, OFFSHORE_SECRECY, SANCTIONS_EXPOSURE, get_jurisdictions,
)
from sentinelai.engine.types import GEOGRAPHIC, EngineInput, Signal

# category -> (code, weight, description template, alert type)
_CATEGORY_RULES = {
    CALL_FOR_ACTION: ("GEO_FATF_CALL_FOR_ACTION", 0.45, "{role} country {country} is on the FATF 'call for action' list", "HIGH_RISK_JURISDICTION"),
    SANCTIONS_EXPOSURE: ("GEO_SANCTIONS_EXPOSURE", 0.32, "{role} country {country} has significant sanctions-programme exposure", "HIGH_RISK_JURISDICTION"),
    INCREASED_MONITORING: ("GEO_FATF_INCREASED_MONITORING", 0.16, "{role} country {country} is under FATF increased monitoring", "HIGH_RISK_JURISDICTION"),
    OFFSHORE_SECRECY: ("GEO_OFFSHORE_SECRECY", 0.13, "{role} country {country} is an offshore/secrecy jurisdiction", None),
}
_ORDER = [CALL_FOR_ACTION, SANCTIONS_EXPOSURE, INCREASED_MONITORING, OFFSHORE_SECRECY]


def detect(ctx: EngineInput) -> List[Signal]:
    j = get_jurisdictions()
    signals: List[Signal] = []
    legs = [("origin", ctx.origin_country), ("destination", ctx.destination_country)]
    legs += [("intermediate", c) for c in ctx.intermediate_countries]

    flagged = []
    for role, country in legs:
        if not country:
            continue
        cats = j.categories(country)
        # a country can be in several lists; report its most severe one only
        for cat in _ORDER:
            if cat in cats:
                code, weight, template, alert = _CATEGORY_RULES[cat]
                signals.append(Signal(
                    code=code, category=GEOGRAPHIC, weight=weight, subject=f"{role}:{country}",
                    description=template.format(role=role.capitalize(), country=f"{j.name(country)} ({country})"),
                    evidence={"country": country, "role": role, "lists": cats}, typology="HIGH_RISK_GEOGRAPHY",
                    alert_type=alert,
                ))
                flagged.append(country)
                break

    if len(ctx.intermediate_countries) >= 2:
        signals.append(Signal(
            code="GEO_COMPLEX_ROUTING", category=GEOGRAPHIC, weight=0.20, subject="routing",
            description=f"Funds routed through {len(ctx.intermediate_countries)} intermediate jurisdictions",
            evidence={"intermediate": ctx.intermediate_countries}, typology="LAYERING", alert_type="UNUSUAL_ACTIVITY",
        ))

    offshore = [c for _, c in legs if c and OFFSHORE_SECRECY in j.categories(c)]
    if len(set(offshore)) >= 2:
        signals.append(Signal(
            code="GEO_OFFSHORE_CHAIN", category=GEOGRAPHIC, weight=0.28, subject="offshore-chain",
            description="Multiple secrecy jurisdictions appear in the payment path",
            evidence={"countries": sorted(set(offshore))}, typology="LAYERING", alert_type="HIGH_RISK_JURISDICTION",
        ))
    return signals
