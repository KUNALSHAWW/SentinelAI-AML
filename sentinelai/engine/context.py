"""Turn raw request dictionaries into a validated :class:`EngineInput`."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from sentinelai.core.fx import to_usd
from sentinelai.core.jurisdictions import get_jurisdictions
from sentinelai.core.regimes import get_regime
from sentinelai.core.time import ensure_utc, utcnow
from sentinelai.engine import names as nm
from sentinelai.engine.types import Edge, EngineInput, HistoryTx


def entity_key(name: Optional[str]) -> str:
    """Stable graph-node key for a party / account name."""
    return nm.normalize(name or "") or (name or "").strip().lower()


def _value(obj: Any) -> Any:
    return getattr(obj, "value", obj)


def build_input(
    transaction: Dict[str, Any],
    customer: Dict[str, Any],
    network_transactions: Optional[List[Dict[str, Any]]] = None,
    regime: Optional[str] = None,
    confidential: bool = False,
    enable_graph: bool = True,
) -> EngineInput:
    j = get_jurisdictions()
    amount = float(transaction.get("amount") or 0)
    currency = (transaction.get("currency") or "USD").upper()
    tx_type = str(_value(transaction.get("transaction_type")) or "UNKNOWN").upper()
    crypto = dict(transaction.get("crypto_details") or {})
    is_crypto = tx_type == "CRYPTO" or str(transaction.get("asset_type") or "").upper() == "CRYPTO" or bool(crypto)

    parties = [str(p) for p in (transaction.get("parties") or []) if p]
    customer_name = str(customer.get("name") or "")
    customer_id = str(customer.get("customer_id") or "") or customer_name
    me = entity_key(customer_id)
    my_name_key = entity_key(customer_name)

    others = [p for p in parties if entity_key(p) not in (me, my_name_key)]
    counterparty = entity_key(others[0]) if others else (entity_key(parties[-1]) if parties else "unknown counterparty")
    incoming = str(_value(transaction.get("direction")) or "OUT").upper() == "IN"
    sender = me if not incoming else counterparty
    receiver = counterparty if not incoming else me
    if transaction.get("sender_account"):
        sender = entity_key(transaction["sender_account"])
    if transaction.get("receiver_account"):
        receiver = entity_key(transaction["receiver_account"])

    history: List[HistoryTx] = []
    for h in customer.get("transaction_history") or []:
        ts = ensure_utc(h.get("timestamp"))
        if ts is None:
            continue
        history.append(HistoryTx(
            amount=float(h.get("amount") or 0), timestamp=ts, currency=(h.get("currency") or "USD").upper(),
            counterparty=h.get("counterparty"), direction=str(_value(h.get("direction")) or "OUT").upper(),
            country=j.normalize(h.get("destination_country") or h.get("country")) or None,
            transaction_type=_value(h.get("transaction_type")),
        ))

    edges: List[Edge] = []
    for n in network_transactions or []:
        ts = ensure_utc(n.get("timestamp"))
        if ts is None or not n.get("sender") or not n.get("receiver"):
            continue
        edges.append(Edge(entity_key(n["sender"]), entity_key(n["receiver"]),
                          to_usd(float(n.get("amount") or 0), n.get("currency") or "USD"), ts, n.get("reference")))

    free_text = [customer_name, str(customer.get("occupation") or ""), str(customer.get("source_of_funds") or ""),
                 str(customer.get("expected_activity") or ""), str(transaction.get("notes") or "")]
    free_text += parties + [str(d) for d in (transaction.get("documents") or [])]
    free_text += [str(h.get("counterparty") or "") for h in (customer.get("transaction_history") or [])]
    trade = dict(transaction.get("trade_details") or {})
    free_text.append(str(trade.get("goods_description") or ""))

    return EngineInput(
        amount=amount,
        currency=currency,
        amount_usd=to_usd(amount, currency),
        transaction_type=tx_type,
        timestamp=ensure_utc(transaction.get("timestamp"), utcnow()),
        origin_country=j.normalize(transaction.get("origin_country")),
        destination_country=j.normalize(transaction.get("destination_country")),
        intermediate_countries=[j.normalize(c) for c in (transaction.get("intermediate_countries") or []) if c],
        parties=parties,
        documents=[str(d) for d in (transaction.get("documents") or [])],
        sender=sender,
        receiver=receiver,
        crypto_details=crypto,
        trade_details=trade,
        is_crypto=is_crypto,
        customer_name=customer_name,
        customer_id=customer_id,
        customer_type=str(customer.get("customer_type") or "INDIVIDUAL").upper(),
        account_age_days=(int(customer["account_age_days"]) if customer.get("account_age_days") is not None else None),
        nationality=j.normalize(customer.get("nationality")),
        residence=j.normalize(customer.get("country_of_residence")),
        occupation=str(customer.get("occupation") or ""),
        history=sorted(history, key=lambda h: h.timestamp),
        network_edges=edges,
        regime=(regime or get_regime().code).upper(),
        confidential=confidential,
        enable_graph=enable_graph,
        notes=str(transaction.get("notes") or ""),
        free_text=[t for t in free_text if t],
    )
