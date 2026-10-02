"""Behavioural signals: structuring, velocity, baselines, new-account abuse."""

from __future__ import annotations

import statistics
from datetime import timedelta
from typing import List

from sentinelai.core.config import settings
from sentinelai.core.fx import convert
from sentinelai.core.regimes import get_regime
from sentinelai.engine.types import BEHAVIORAL, EngineInput, Signal

# Window over which repeated just-below-threshold transactions are treated as one
# structured scheme (structuring is typically spread over days; India aggregates
# "integrally connected" cash transactions over a calendar month).
_AGGREGATION_HOURS = {"US_BSA": 24 * 7, "EU_AMLD": 24 * 7, "IN_PMLA": 24 * 30}


def detect(ctx: EngineInput) -> List[Signal]:
    cfg = settings.risk
    regime = get_regime(ctx.regime)
    signals: List[Signal] = []

    threshold = regime.cash_report_threshold                      # in regime currency
    amount_local = convert(ctx.amount, ctx.currency, regime.currency)
    band_low = threshold * regime.structuring_band
    is_cash = ctx.transaction_type == "CASH"
    window = timedelta(hours=_AGGREGATION_HOURS.get(regime.code, 24))
    fmt = f"{regime.currency} {{:,.0f}}".format

    # --- single transaction just below the reporting threshold ---------------
    if band_low <= amount_local < threshold:
        signals.append(Signal(
            code="BEH_NEAR_THRESHOLD", category=BEHAVIORAL, weight=0.36 if is_cash else 0.24, subject="amount",
            description=f"Amount {fmt(amount_local)} sits just below the {regime.cash_report} threshold {fmt(threshold)}",
            evidence={"amount_local": round(amount_local, 2), "threshold": threshold, "regime": regime.code},
            typology="STRUCTURING", alert_type="STRUCTURING"))

    # --- connected sub-threshold transactions that add up past the threshold --
    recent = [h for h in ctx.history if abs((ctx.timestamp - h.timestamp).total_seconds()) <= window.total_seconds()]
    local_amounts = [convert(h.amount, h.currency, regime.currency) for h in recent] + [amount_local]
    sub_threshold = [a for a in local_amounts if band_low * 0.8 <= a < threshold]
    if len(local_amounts) >= 3 and len(sub_threshold) >= 3 and sum(local_amounts) >= threshold:
        signals.append(Signal(
            code="BEH_STRUCTURING_PATTERN", category=BEHAVIORAL, weight=0.72 if is_cash else 0.55, subject="pattern",
            description=f"{len(sub_threshold)} connected transactions just below {fmt(threshold)} totalling {fmt(sum(local_amounts))}",
            evidence={"count": len(sub_threshold), "total_local": round(sum(local_amounts), 2),
                      "window_hours": int(window.total_seconds() // 3600)},
            typology="STRUCTURING", alert_type="STRUCTURING"))

    # --- size ----------------------------------------------------------------
    if ctx.amount_usd > cfg.very_large_transaction_threshold:
        signals.append(Signal(
            code="BEH_VERY_LARGE", category=BEHAVIORAL, weight=0.20, subject="size",
            description=f"Very large transaction (USD {ctx.amount_usd:,.0f})", evidence={"amount_usd": round(ctx.amount_usd, 2)},
            typology="ANOMALOUS_BEHAVIOR", alert_type="UNUSUAL_ACTIVITY"))
    elif ctx.amount_usd > cfg.large_transaction_threshold:
        signals.append(Signal(
            code="BEH_LARGE", category=BEHAVIORAL, weight=0.08, subject="size",
            description=f"Large transaction (USD {ctx.amount_usd:,.0f})", evidence={"amount_usd": round(ctx.amount_usd, 2)},
            typology="ANOMALOUS_BEHAVIOR"))

    # --- velocity (24 h) -----------------------------------------------------
    day = [h for h in ctx.history if abs((ctx.timestamp - h.timestamp).total_seconds()) < 86400]
    if len(day) + 1 >= cfg.max_daily_transactions:
        signals.append(Signal(
            code="BEH_HIGH_VELOCITY", category=BEHAVIORAL, weight=0.24, subject="velocity",
            description=f"{len(day) + 1} transactions within 24 hours", evidence={"count_24h": len(day) + 1},
            typology="ANOMALOUS_BEHAVIOR", alert_type="VELOCITY_BREACH"))
    daily_total = sum(h.amount_usd for h in day) + ctx.amount_usd
    if daily_total > cfg.max_daily_amount and len(day) >= 1:
        signals.append(Signal(
            code="BEH_DAILY_VOLUME", category=BEHAVIORAL, weight=0.18, subject="daily-volume",
            description=f"24-hour volume USD {daily_total:,.0f} exceeds USD {cfg.max_daily_amount:,.0f}",
            evidence={"daily_total_usd": round(daily_total, 2)}, typology="ANOMALOUS_BEHAVIOR", alert_type="VELOCITY_BREACH"))

    # --- uniform amounts -----------------------------------------------------
    amounts = [h.amount_usd for h in day] + [ctx.amount_usd]
    if len(amounts) >= 3 and statistics.mean(amounts) > 0:
        if statistics.pstdev(amounts) / statistics.mean(amounts) < 0.05:
            signals.append(Signal(
                code="BEH_UNIFORM_AMOUNTS", category=BEHAVIORAL, weight=0.18, subject="uniform",
                description="Near-identical amounts across recent transactions (scripted behaviour)",
                evidence={"n": len(amounts)}, typology="STRUCTURING"))

    # --- deviation from the customer's own baseline ---------------------------
    prior = [h.amount_usd for h in ctx.history]
    if len(prior) >= 5:
        mean, sd, median = statistics.mean(prior), statistics.pstdev(prior), statistics.median(prior)
        if ctx.amount_usd > mean + 3 * max(sd, 0.1 * mean) and ctx.amount_usd > 3 * median:
            signals.append(Signal(
                code="BEH_BASELINE_DEVIATION", category=BEHAVIORAL, weight=0.22, subject="baseline",
                description=f"Amount is {ctx.amount_usd / max(median, 1):.1f}x the customer's median ({median:,.0f} USD)",
                evidence={"median_usd": round(median, 2), "mean_usd": round(mean, 2), "history_n": len(prior)},
                typology="ANOMALOUS_BEHAVIOR", alert_type="UNUSUAL_ACTIVITY"))

    # --- new account ---------------------------------------------------------
    if ctx.account_age_days is not None and ctx.account_age_days < cfg.new_account_days:
        if ctx.amount_usd > cfg.large_transaction_threshold:
            signals.append(Signal(
                code="BEH_NEW_ACCOUNT_HIGH_VALUE", category=BEHAVIORAL, weight=0.30, subject="new-account",
                description=f"High-value transaction on a {ctx.account_age_days}-day-old account",
                evidence={"account_age_days": ctx.account_age_days}, typology="NEW_ACCOUNT_ABUSE", alert_type="UNUSUAL_ACTIVITY"))
        if len(ctx.history) >= 3:
            signals.append(Signal(
                code="BEH_NEW_ACCOUNT_VELOCITY", category=BEHAVIORAL, weight=0.18, subject="new-account-velocity",
                description=f"{len(ctx.history)} prior transactions on a {ctx.account_age_days}-day-old account",
                typology="NEW_ACCOUNT_ABUSE"))

    # --- round amounts ---------------------------------------------------------
    if ctx.amount >= 10_000 and ctx.amount % 1000 == 0:
        signals.append(Signal(
            code="BEH_ROUND_AMOUNT", category=BEHAVIORAL, weight=0.05, subject="round",
            description="Round-number amount", evidence={"amount": ctx.amount}, typology="ANOMALOUS_BEHAVIOR"))
    return signals
