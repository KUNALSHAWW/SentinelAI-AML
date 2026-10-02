"""
Deterministic detection pipeline
================================

Runs every detector over a normalised :class:`EngineInput` and fuses the
resulting signals into an explainable score. No network, no LLM, no database:
this is the always-available core that the LLM research layer only *adds to*.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from sentinelai.core.config import settings
from sentinelai.core.fx import convert
from sentinelai.core.regimes import get_regime
from sentinelai.engine import behavioral, crypto, geo, graph, hygiene, trade
from sentinelai.engine import names as nm
from sentinelai.engine.pep import PEPScreener, get_pep_screener
from sentinelai.engine.sanctions import SanctionsScreener, get_screener
from sentinelai.engine.scoring import ScoreResult, combine, decide
from sentinelai.engine.types import (
    CUSTOMER,
    INTEGRITY,
    PEP,
    SANCTIONS,
    Edge,
    EngineInput,
    Signal,
)
from sentinelai.engine.typologies import describe


@dataclass
class EngineResult:
    ctx: EngineInput
    signals: List[Signal]
    score: ScoreResult
    decision: Dict[str, Any]
    sanctions_matches: List[Dict[str, Any]] = field(default_factory=list)
    pep: Dict[str, Any] = field(default_factory=dict)
    graph: graph.GraphFindings = field(default_factory=graph.GraphFindings)
    typologies: List[Dict[str, Any]] = field(default_factory=list)
    injection_hits: List[Dict[str, str]] = field(default_factory=list)
    sanctions_info: Dict[str, Any] = field(default_factory=dict)


class DetectionEngine:
    def __init__(self, sanctions: Optional[SanctionsScreener] = None, peps: Optional[PEPScreener] = None):
        self._sanctions = sanctions
        self._peps = peps

    @property
    def sanctions(self) -> SanctionsScreener:
        return self._sanctions or get_screener()

    @property
    def peps(self) -> PEPScreener:
        return self._peps or get_pep_screener()

    # ------------------------------------------------------------------
    def screen_sanctions(self, ctx: EngineInput):
        """Screen the customer and every named party; returns (signals, match dicts)."""
        signals: List[Signal] = []
        matches: List[Dict[str, Any]] = []
        corroborating = [ctx.origin_country, ctx.destination_country, ctx.nationality, ctx.residence,
                         *ctx.intermediate_countries]
        subjects = [("customer", ctx.customer_name)] + [("party", p) for p in ctx.parties]
        seen = set()
        for role, name in subjects:
            key = nm.normalize(name)
            if not key or key in seen:
                continue
            seen.add(key)
            for m in self.sanctions.screen(name, corroborating):
                d = m.to_dict() | {"role": role}
                matches.append(d)
                text = f"{role.capitalize()} '{name}' vs {m.list_name} '{m.listed_name}' (similarity {m.score:.2f})"
                if m.level == "MATCH":
                    signals.append(Signal(
                        code="SANCTIONS_MATCH", category=SANCTIONS, weight=0.97, floor=95, subject=key,
                        description=f"Sanctions MATCH - {text}", evidence=d, typology="SANCTIONS_EVASION",
                        alert_type="SANCTIONS_HIT"))
                elif m.level == "STRONG_POTENTIAL_MATCH":
                    signals.append(Signal(
                        code="SANCTIONS_STRONG_POTENTIAL", category=SANCTIONS,
                        weight=0.80 if m.corroborated_by else 0.66, subject=key,
                        description=f"Strong potential sanctions match - {text}", evidence=d,
                        typology="SANCTIONS_EVASION", alert_type="SANCTIONS_HIT"))
                else:
                    signals.append(Signal(
                        code="SANCTIONS_POTENTIAL", category=SANCTIONS, weight=0.38, subject=key,
                        description=f"Potential sanctions match (analyst review) - {text}", evidence=d,
                        typology="SANCTIONS_EVASION", alert_type="SANCTIONS_HIT"))
                break  # strongest hit per subject is enough for scoring
        return signals, matches

    def screen_pep(self, ctx: EngineInput):
        res = self.peps.screen(ctx.customer_name, ctx.occupation)
        signals: List[Signal] = []
        if res.list_matches:
            m = res.list_matches[0]
            signals.append(Signal(
                code="PEP_MATCH", category=PEP, weight=0.40, subject=ctx.customer_name,
                floor=settings.risk.medium_risk_threshold,          # FATF R12: a listed PEP always warrants enhanced due diligence
                description=f"Customer matches PEP list entry '{m['listed_name']}' ({m.get('position') or 'PEP'}, {m.get('country')})",
                evidence=m, typology="PEP_EXPOSURE", alert_type="PEP_MATCH"))
        elif res.role_indicators:
            r = res.role_indicators[0]
            signals.append(Signal(
                code="PEP_ROLE_INDICATOR", category=PEP, weight=0.22, subject=ctx.customer_name,
                description=f"Customer name/occupation indicates a public role: {r['role']} ('{r['matched_text']}')",
                evidence=r, typology="PEP_EXPOSURE", alert_type="PEP_MATCH"))
        return signals, {"list_matches": res.list_matches, "role_indicators": res.role_indicators,
                         "is_pep_candidate": res.is_pep_candidate}

    def customer_signals(self, ctx: EngineInput) -> List[Signal]:
        """Shell-company indicators: young corporate + secrecy jurisdiction + thin documentation."""
        from sentinelai.core.jurisdictions import OFFSHORE_SECRECY, get_jurisdictions
        j = get_jurisdictions()
        out: List[Signal] = []
        legs = [ctx.origin_country, ctx.destination_country, *ctx.intermediate_countries]
        offshore = any(OFFSHORE_SECRECY in j.categories(c) for c in legs if c)
        young = ctx.account_age_days is not None and ctx.account_age_days < 180
        if ctx.customer_type in ("CORPORATE", "COMPANY") and young and offshore and not ctx.documents:
            out.append(Signal(
                code="CUST_SHELL_INDICATORS", category=CUSTOMER, weight=0.30, subject="shell",
                description="Young corporate account paying a secrecy jurisdiction with no supporting documents",
                evidence={"account_age_days": ctx.account_age_days}, typology="SHELL_COMPANY",
                alert_type="NETWORK_ANOMALY"))
        return out

    # ------------------------------------------------------------------
    def run(self, ctx: EngineInput, extra_edges: Optional[List[Edge]] = None) -> EngineResult:
        signals: List[Signal] = []
        sanction_signals, sanctions_matches = self.screen_sanctions(ctx)
        pep_signals, pep_info = self.screen_pep(ctx)
        graph_findings = graph.analyze(ctx, extra_edges) if ctx.enable_graph else graph.GraphFindings()

        signals += sanction_signals + pep_signals
        signals += geo.detect(ctx) + behavioral.detect(ctx) + crypto.detect(ctx) + trade.detect(ctx)
        signals += graph_findings.signals + self.customer_signals(ctx)

        injection = hygiene.detect_injection(ctx.free_text)
        if injection:
            signals.append(Signal(
                code="INTEGRITY_INPUT_MANIPULATION", category=INTEGRITY, weight=0.45, subject="injection",
                description="Free-text fields contain instructions aimed at an automated reviewer",
                evidence={"hits": injection[:3]}, typology="INPUT_MANIPULATION", alert_type="UNUSUAL_ACTIVITY"))

        score = combine(signals)
        decision = decide(score, signals)
        return EngineResult(
            ctx=ctx, signals=signals, score=score, decision=decision, sanctions_matches=sanctions_matches,
            pep=pep_info, graph=graph_findings, typologies=typology_summary(signals), injection_hits=injection,
            sanctions_info=self.sanctions.info,
        )


def typology_summary(signals: List[Signal]) -> List[Dict[str, Any]]:
    grouped: Dict[str, List[str]] = {}
    for s in signals:
        if s.typology:
            grouped.setdefault(s.typology, []).append(s.code)
    out = []
    for key, codes in grouped.items():
        info = describe(key)
        out.append({"id": key, "name": info["name"], "summary": info["summary"],
                    "reference": info["reference"], "signals": sorted(set(codes))})
    return sorted(out, key=lambda t: -len(t["signals"]))


def reporting_threshold_info(ctx: EngineInput) -> Dict[str, Any]:
    regime = get_regime(ctx.regime)
    return {
        "regime": regime.code, "currency": regime.currency, "threshold": regime.cash_report_threshold,
        "amount_in_regime_currency": round(convert(ctx.amount, ctx.currency, regime.currency), 2),
    }
