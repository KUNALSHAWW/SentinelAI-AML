"""Virtual-asset risk signals."""

from __future__ import annotations

from typing import List

from sentinelai.engine.types import CRYPTO, EngineInput, Signal

KNOWN_MIXERS = ("tornado", "wasabi", "samourai", "chipmixer", "blender", "sinbad", "coinjoin")
KNOWN_DARKNET = ("hydra", "alphabay", "dark0de", "versus", "world market", "silk road", "monopoly")


def detect(ctx: EngineInput) -> List[Signal]:
    if not ctx.is_crypto:
        return []
    d = ctx.crypto_details
    out: List[Signal] = []

    def add(code, weight, text, typology="CRYPTO_OBFUSCATION", alert="CRYPTO_RISK", **evidence):
        out.append(Signal(code=code, category=CRYPTO, weight=weight, description=text, evidence=evidence,
                          typology=typology, alert_type=alert, subject=code))

    mixer_service = str(d.get("mixer_service") or "").lower()
    if d.get("mixer_used") or any(m in mixer_service for m in KNOWN_MIXERS):
        add("CRYPTO_MIXER", 0.50, "Funds passed through a mixing/tumbling service", mixer_service=mixer_service or None)
    market = str(d.get("darknet_market") or "").lower()
    if market and any(m in market for m in KNOWN_DARKNET):
        add("CRYPTO_DARKNET", 0.80, f"Exposure to darknet market '{d.get('darknet_market')}'", market=d.get("darknet_market"))
    elif market:
        add("CRYPTO_DARKNET_UNVERIFIED", 0.35, f"Darknet association reported: '{d.get('darknet_market')}'", market=market)

    age = d.get("wallet_age_days")
    if isinstance(age, (int, float)):
        if age < 7:
            add("CRYPTO_NEW_WALLET", 0.25, f"Wallet is only {int(age)} days old", wallet_age_days=age)
        elif age < 30:
            add("CRYPTO_RECENT_WALLET", 0.12, f"Wallet is only {int(age)} days old", wallet_age_days=age)

    swaps = int(d.get("cross_chain_swaps") or 0)
    if swaps >= 3:
        add("CRYPTO_LAYERING", 0.40, f"{swaps} cross-chain swaps (chain-hopping)", swaps=swaps)
    elif swaps >= 1:
        add("CRYPTO_CROSS_CHAIN", 0.10, f"{swaps} cross-chain swap(s)", swaps=swaps)
    if d.get("privacy_coin"):
        add("CRYPTO_PRIVACY_COIN", 0.40, "Conversion into a privacy-enhanced coin")
    if ctx.amount_usd > 100_000:
        add("CRYPTO_HIGH_VALUE", 0.10, f"High-value virtual-asset transfer (USD {ctx.amount_usd:,.0f})",
            typology="ANOMALOUS_BEHAVIOR", alert="UNUSUAL_ACTIVITY")
    return out
