"""
Typology catalogue
==================

Each detection signal maps to a documented money-laundering typology so every
alert can cite *why it matters* and where the red flag comes from. Sources are
public regulator/FATF material; this is a reference aid, not legal advice.
"""

from __future__ import annotations

from typing import Dict

TYPOLOGIES: Dict[str, Dict[str, str]] = {
    "STRUCTURING": {
        "name": "Structuring / smurfing",
        "summary": "Breaking cash or value into amounts just below a reporting threshold to avoid a report.",
        "reference": "31 U.S.C. 5324 (structuring); FinCEN SAR guidance; PMLA Rules 2005 (connected-series CTR).",
    },
    "ROUND_TRIPPING": {
        "name": "Round-tripping",
        "summary": "Funds return to the originator through intermediaries to give them a legitimate appearance.",
        "reference": "FATF ML typology reports (layering through circular flows).",
    },
    "FAN_IN": {
        "name": "Fan-in / mule collection",
        "summary": "Many unrelated senders funnel funds into one account (money-mule or collection account).",
        "reference": "FATF guidance on money-mule networks; graph-AML literature (fan-in motif).",
    },
    "FAN_OUT": {
        "name": "Fan-out / dispersion",
        "summary": "One account rapidly distributes funds to many beneficiaries (placement/layering).",
        "reference": "FATF ML typology reports; graph-AML literature (fan-out motif).",
    },
    "PASS_THROUGH": {
        "name": "Rapid movement / pass-through account",
        "summary": "Funds received and forwarded almost immediately with little retained balance.",
        "reference": "FATF red-flag indicators (rapid movement of funds); FIU-IND red-flag indicators.",
    },
    "LAYERING": {
        "name": "Layering via complex routing",
        "summary": "Multi-jurisdiction routing or chained intermediaries that obscure the funds' trail.",
        "reference": "FATF 40 Recommendations / typology reports (layering stage).",
    },
    "SANCTIONS_EVASION": {
        "name": "Sanctions exposure / evasion",
        "summary": "Dealings with a listed party, or routing designed to obscure a listed party's involvement.",
        "reference": "FATF Recommendation 6 (targeted financial sanctions); OFAC SDN / UN / EU lists.",
    },
    "PEP_EXPOSURE": {
        "name": "Politically exposed person",
        "summary": "Customer or beneficial owner holds a prominent public function; elevated corruption risk.",
        "reference": "FATF Recommendations 12 and 22; FATF Guidance on PEPs (2013).",
    },
    "TBML": {
        "name": "Trade-based money laundering",
        "summary": "Over/under-invoicing, phantom shipments or misdescribed goods to move value via trade.",
        "reference": "FATF/Egmont TBML report (2020); FinCEN Advisory FIN-2010-A001.",
    },
    "CRYPTO_OBFUSCATION": {
        "name": "Virtual-asset obfuscation",
        "summary": "Mixers, privacy coins, cross-chain hopping or darknet exposure to break traceability.",
        "reference": "FATF Updated Guidance for a Risk-Based Approach to Virtual Assets (2021).",
    },
    "HIGH_RISK_GEOGRAPHY": {
        "name": "High-risk jurisdiction exposure",
        "summary": "Flows involving FATF-listed, heavily sanctioned or secrecy jurisdictions.",
        "reference": "FATF 'call for action' and 'increased monitoring' lists.",
    },
    "NEW_ACCOUNT_ABUSE": {
        "name": "New-account / rapid-activation abuse",
        "summary": "High-value or high-velocity activity on a recently opened account.",
        "reference": "FinCEN and FIU-IND red-flag indicators for account opening.",
    },
    "ANOMALOUS_BEHAVIOR": {
        "name": "Deviation from customer baseline",
        "summary": "Activity inconsistent with the customer's historical pattern or expected profile.",
        "reference": "Risk-based approach: ongoing monitoring (FATF R.10).",
    },
    "SHELL_COMPANY": {
        "name": "Shell-company indicators",
        "summary": "Young corporate entity, secrecy jurisdiction and thin documentation combine.",
        "reference": "FATF Guidance on beneficial ownership of legal persons (R.24).",
    },
    "INPUT_MANIPULATION": {
        "name": "Attempted manipulation of the screening system",
        "summary": "Free-text fields contain instructions aimed at an automated/LLM reviewer.",
        "reference": "OWASP Top 10 for LLM Applications (prompt injection).",
    },
}


def describe(typology: str) -> Dict[str, str]:
    return TYPOLOGIES.get(typology, {"name": typology, "summary": "", "reference": ""})
