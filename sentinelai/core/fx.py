"""
Indicative FX conversion
========================

Thresholds are expressed per regime currency, but transactions arrive in any
currency. This module converts through USD using a small static table.

The rates are **indicative only**. Override them with
``SENTINEL_RISK_FX_RATES='{"INR":0.0113}'`` or plug in a live feed.
"""

from __future__ import annotations

from typing import Dict

from sentinelai.core.config import settings

# USD per 1 unit of currency.
DEFAULT_RATES: Dict[str, float] = {
    "USD": 1.0, "EUR": 1.08, "GBP": 1.27, "INR": 0.0113, "CAD": 0.73, "AUD": 0.65,
    "CHF": 1.12, "JPY": 0.0067, "CNY": 0.14, "SGD": 0.74, "AED": 0.2723, "HKD": 0.128,
    "BRL": 0.18, "ZAR": 0.055, "NGN": 0.00065, "RUB": 0.011, "TRY": 0.029, "MXN": 0.052,
    "BTC": 65000.0, "ETH": 3200.0, "USDT": 1.0, "USDC": 1.0,
}


def rates() -> Dict[str, float]:
    return {**DEFAULT_RATES, **{k.upper(): v for k, v in settings.risk.fx_rates.items()}}


def to_usd(amount: float, currency: str = "USD") -> float:
    rate = rates().get((currency or "USD").upper())
    if rate is None:
        return float(amount)  # unknown currency: assume already USD-like, never crash
    return float(amount) * rate


def convert(amount: float, from_currency: str, to_currency: str) -> float:
    rate_to = rates().get((to_currency or "USD").upper(), 1.0)
    return to_usd(amount, from_currency) / rate_to if rate_to else float(amount)
