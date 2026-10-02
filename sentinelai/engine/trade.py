"""Trade-based money-laundering (TBML) signals."""

from __future__ import annotations

import re
from typing import List

from sentinelai.engine.types import TRADE, EngineInput, Signal

_VAGUE = re.compile(r"\b(misc(?:ellaneous)?|general goods|various|assorted|sundry|other goods|consulting)\b", re.I)


def detect(ctx: EngineInput) -> List[Signal]:
    out: List[Signal] = []
    t = ctx.trade_details
    is_trade = ctx.transaction_type == "TRADE_FINANCE" or bool(t)
    cross_border = ctx.origin_country and ctx.destination_country and ctx.origin_country != ctx.destination_country

    invoice, market = t.get("invoice_value"), t.get("market_value_estimate")
    if isinstance(invoice, (int, float)) and isinstance(market, (int, float)) and market > 0:
        deviation = (invoice - market) / market
        direction = "over" if deviation > 0 else "under"
        if abs(deviation) >= 0.5:
            weight = 0.62
        elif abs(deviation) >= 0.25:
            weight = 0.35
        else:
            weight = 0
        if weight:
            out.append(Signal(
                code="TBML_OVER_INVOICING" if deviation > 0 else "TBML_UNDER_INVOICING", category=TRADE, weight=weight,
                subject="price", description=f"Invoice is {abs(deviation):.0%} {direction} the market-value estimate",
                evidence={"invoice_value": invoice, "market_value_estimate": market, "deviation": round(deviation, 3)},
                typology="TBML", alert_type="DOCUMENT_MISMATCH"))

    goods = str(t.get("goods_description") or "")
    if is_trade and (not goods.strip() or _VAGUE.search(goods)):
        out.append(Signal(
            code="TBML_VAGUE_GOODS", category=TRADE, weight=0.22, subject="goods",
            description="Goods description missing or non-specific", evidence={"goods_description": goods or None},
            typology="TBML", alert_type="DOCUMENT_MISMATCH"))

    if (ctx.transaction_type == "TRADE_FINANCE" or (cross_border and ctx.amount_usd >= 50_000 and ctx.transaction_type == "WIRE_TRANSFER")) \
            and not ctx.documents:
        out.append(Signal(
            code="DOC_MISSING_SUPPORT", category=TRADE, weight=0.20 if ctx.transaction_type == "TRADE_FINANCE" else 0.14,
            subject="docs", description="Large cross-border payment without supporting documentation",
            evidence={"amount_usd": round(ctx.amount_usd, 2)}, typology="TBML", alert_type="DOCUMENT_MISMATCH"))

    quantity, unit_price = t.get("quantity"), t.get("unit_price")
    if isinstance(quantity, (int, float)) and isinstance(unit_price, (int, float)) and isinstance(invoice, (int, float)) and invoice > 0:
        implied = quantity * unit_price
        if abs(implied - invoice) / invoice > 0.1:
            out.append(Signal(
                code="DOC_ARITHMETIC_MISMATCH", category=TRADE, weight=0.30, subject="arithmetic",
                description="Invoice total does not equal quantity x unit price",
                evidence={"invoice_value": invoice, "implied_total": implied}, typology="TBML", alert_type="DOCUMENT_MISMATCH"))
    return out
