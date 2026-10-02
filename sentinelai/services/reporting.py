"""
SAR / STR drafting
==================

Builds a regulator-ready *draft* from the engine's facts, using FinCEN's
who / what / when / where / why / how narrative structure (introduction, body,
conclusion). The narrative is deterministic and fully traceable to signals; an
optional LLM rewrite may be attached but is clearly labelled and never replaces it.
Drafts always require analyst review before filing.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from sentinelai.core.regimes import get_regime
from sentinelai.core.time import utcnow
from sentinelai.engine.pipeline import EngineResult
from sentinelai.engine.scoring import ScoreResult
from sentinelai.engine.types import Signal
from sentinelai.engine.typologies import describe


def _money(amount: float, currency: str) -> str:
    return f"{currency} {amount:,.2f}"


def build_report(
    engine: EngineResult,
    score: ScoreResult,
    decision: Dict[str, Any],
    signals: List[Signal],
    case_number: Optional[str] = None,
    ai_findings: Optional[List[Dict[str, Any]]] = None,
    now: Optional[datetime] = None,
) -> Dict[str, Any]:
    ctx = engine.ctx
    regime = get_regime(ctx.regime)
    now = now or utcnow()
    deadline = regime.filing_deadline(now)

    route = " -> ".join([c for c in [ctx.origin_country, *ctx.intermediate_countries, ctx.destination_country] if c]) or "not available"
    red_flags = [
        {"code": s.code, "description": s.description, "severity": s.severity,
         "typology": describe(s.typology)["name"] if s.typology else None,
         "reference": describe(s.typology)["reference"] if s.typology else None, "verified": s.verified}
        for s in sorted(signals, key=lambda s: -s.weight)
    ]
    top = [c for c in score.contributions if c["code"] != "POLICY_FLOOR"][:5]
    why = "; ".join(c["description"] for c in top) or "No individual red flag exceeded the reporting threshold."
    typology_names = ", ".join(t["name"] for t in engine.typologies) or "none identified"
    sanctions_text = "; ".join(
        f"{m['role']} '{m['queried_name']}' matched {m['list']} '{m['listed_name']}' (similarity {m['score']})"
        for m in engine.sanctions_matches) or "no sanctions list hits"

    intro = (
        f"This {regime.suspicious_report} draft concerns {ctx.customer_name or 'the customer'} "
        f"({ctx.customer_type.title()}{', account age ' + str(ctx.account_age_days) + ' days' if ctx.account_age_days is not None else ''}). "
        f"Automated monitoring assigned a risk score of {score.score}/100 ({score.level}) and recommended: "
        f"{decision['recommended_action']}."
    )
    body = {
        "who": f"Subject: {ctx.customer_name or 'unknown'}; customer type {ctx.customer_type}; nationality "
               f"{ctx.nationality or 'not available'}; residence {ctx.residence or 'not available'}; occupation "
               f"{ctx.occupation or 'not available'}. Other parties: {', '.join(ctx.parties) or 'none named'}.",
        "what": f"A {ctx.transaction_type.replace('_', ' ').lower()} of {_money(ctx.amount, ctx.currency)} "
                f"(approx. USD {ctx.amount_usd:,.2f}). Documents supplied: {', '.join(ctx.documents) or 'none'}.",
        "when": f"Transaction timestamp {ctx.timestamp.isoformat()}; {len(ctx.history)} prior transactions considered.",
        "where": f"Jurisdictions on the payment path: {route}.",
        "why": f"The activity is considered suspicious because: {why}. Typologies: {typology_names}. Screening: {sanctions_text}.",
        "how": "Detected by deterministic rules (geography, behaviour, sanctions/PEP screening, trade and crypto checks) "
               "and transaction-graph analysis, fused by an explainable noisy-OR model"
               + ("; AI research findings were considered as advisory evidence only." if ai_findings else "."),
    }
    conclusion = (
        f"Based on the above, filing a {regime.suspicious_report} is "
        f"{'recommended' if decision['report_required'] else 'not currently required, but monitoring should continue'}. "
        f"{regime.deadline_note}"
    )
    report = {
        "report_type": regime.suspicious_report,
        "regulator": regime.regulator,
        "regime": regime.code,
        "status": "DRAFT - analyst review required before filing",
        "case_number": case_number,
        "generated_at": now.isoformat(),
        "filing_deadline": deadline.isoformat() if deadline else None,
        "deadline_note": regime.deadline_note,
        "subject": {"name": ctx.customer_name, "customer_id": ctx.customer_id, "type": ctx.customer_type,
                    "account_age_days": ctx.account_age_days, "nationality": ctx.nationality,
                    "residence": ctx.residence, "occupation": ctx.occupation},
        "activity": {"amount": ctx.amount, "currency": ctx.currency, "amount_usd": round(ctx.amount_usd, 2),
                     "transaction_type": ctx.transaction_type, "timestamp": ctx.timestamp.isoformat(),
                     "route": route, "parties": ctx.parties, "documents": ctx.documents},
        "risk": {"score": score.score, "level": score.level, "recommended_action": decision["recommended_action"],
                 "report_required": decision["report_required"]},
        "red_flags": red_flags,
        "typologies": engine.typologies,
        "narrative": {"introduction": intro, "body": body, "conclusion": conclusion},
        "limitations": [
            "Generated from the data supplied with the request only.",
            "Sanctions matching is name-based; confirm against identifiers (DOB, registration no.) before action.",
            "AI findings, where present, are unverified and advisory.",
        ],
    }
    report["narrative_text"] = narrative_text(report)
    return report


def narrative_text(report: Dict[str, Any]) -> str:
    n = report["narrative"]
    parts = [n["introduction"], ""]
    for key in ("who", "what", "when", "where", "why", "how"):
        parts.append(f"{key.upper()}: {n['body'][key]}")
    parts += ["", n["conclusion"]]
    return "\n".join(parts)


def to_markdown(report: Dict[str, Any]) -> str:
    r = report
    lines = [
        f"# {r['report_type']} draft - {r.get('case_number') or 'unassigned'}",
        f"**Status:** {r['status']}  ",
        f"**Regulator:** {r['regulator']} | **Regime:** {r['regime']}  ",
        f"**Generated:** {r['generated_at']} | **Filing deadline:** {r['filing_deadline'] or 'without delay'}",
        "", f"> {r['deadline_note']}", "", "## Subject",
    ]
    lines += [f"- **{k.replace('_', ' ').title()}:** {v if v not in (None, '') else 'not available'}" for k, v in r["subject"].items()]
    lines += ["", "## Activity"]
    lines += [f"- **{k.replace('_', ' ').title()}:** {v if v not in (None, '', []) else 'not available'}" for k, v in r["activity"].items()]
    lines += ["", f"## Risk assessment\nScore **{r['risk']['score']}/100 ({r['risk']['level']})** - "
                  f"action: **{r['risk']['recommended_action']}**", "", "## Red flags"]
    lines += [f"- [{f['severity']}] {f['description']}" + (f" _(typology: {f['typology']})_" if f["typology"] else "")
              + ("" if f["verified"] else " _[unverified AI evidence]_") for f in r["red_flags"]]
    lines += ["", "## Narrative", "", r["narrative_text"], "", "## Limitations"]
    lines += [f"- {x}" for x in r["limitations"]]
    return "\n".join(lines)
