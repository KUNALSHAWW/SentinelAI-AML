"""
Synthetic labelled AML dataset generator
========================================

Produces reproducible (seeded) transaction scenarios with ground-truth labels,
in the spirit of AMLSim / AMLgentex: a mix of benign behaviour - including
deliberately *hard negatives* that superficially resemble red flags - and
injected typologies.

HONEST CAVEAT: the generator and the detection engine were written by the same
team, so absolute scores are optimistic compared with real bank data. The value
is regression protection, ablation evidence (what each detector contributes) and
a fair comparison against a naive threshold baseline on identical data.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Dict, List, Optional

FIRST = ["Aarav", "Priya", "Rahul", "Sneha", "Wei", "Li", "Chen", "Mei", "John", "Emily", "Michael", "Sarah", "Carlos", "Maria",
         "Ahmed", "Fatima", "Omar", "Layla", "Ivan", "Olga", "Hans", "Greta", "Pierre", "Sophie", "Kenji", "Yuki", "Tariq", "Aisha",
         "Lucas", "Emma", "Noah", "Olivia", "Diego", "Valentina", "Arjun", "Divya", "Samuel", "Grace", "Daniel", "Hannah"]
LAST = ["Sharma", "Patel", "Singh", "Gupta", "Wang", "Zhang", "Liu", "Smith", "Johnson", "Brown", "Garcia", "Martinez", "Khan",
        "Hussain", "Petrov", "Ivanova", "Mueller", "Schmidt", "Dubois", "Laurent", "Tanaka", "Sato", "Rossi", "Silva", "Costa",
        "Nguyen", "Kim", "Park", "Okafor", "Mensah", "Fischer", "Weber", "Moreau", "Lopez", "Reddy", "Nair", "Iyer", "Das"]
COMPANY_A = ["Apex", "Summit", "Blue Harbor", "Northwind", "Silverline", "Orion", "Crescent", "Evergreen", "Pioneer", "Cobalt",
             "Redwood", "Lakeside", "Granite", "Maple", "Falcon", "Harvest", "Atlas", "Sterling", "Beacon", "Willow"]
COMPANY_B = ["Logistics", "Foods", "Textiles", "Engineering", "Pharma", "Software", "Constructions", "Traders", "Industries",
             "Agro", "Electronics", "Packaging", "Consulting", "Services", "Metals"]
LEGIT_COUNTRIES = ["US", "CA", "GB", "DE", "FR", "IN", "JP", "AU", "SG", "NL", "CH", "LU", "AE", "IE", "ES", "IT"]
DOMESTIC = {"US_BSA": "US", "IN_PMLA": "IN", "EU_AMLD": "DE"}


@dataclass
class Sample:
    id: str
    request: Dict[str, Any]
    label: int                      # 1 = suspicious / should be flagged
    typology: Optional[str]
    hard_negative: bool = False


def _person(r: random.Random) -> str:
    return f"{r.choice(FIRST)} {r.choice(LAST)}"


def _company(r: random.Random) -> str:
    return f"{r.choice(COMPANY_A)} {r.choice(COMPANY_B)}"


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat()


class Builder:
    def __init__(self, seed: int, now: datetime):
        self.r = random.Random(seed)
        self.now = now
        self.n = 0

    # -- helpers -----------------------------------------------------------
    def ts(self, hours_ago: float) -> str:
        return _iso(self.now - timedelta(hours=hours_ago))

    def cid(self) -> str:
        self.n += 1
        return f"cust-{self.n:06d}"

    def history(self, n: int, lo: float, hi: float, span_h: float, currency="USD", counterparties=None,
                direction="OUT", ttype=None) -> List[Dict[str, Any]]:
        out = []
        for i in range(n):
            h = {"amount": round(self.r.uniform(lo, hi), 2), "currency": currency,
                 "timestamp": self.ts(self.r.uniform(2, span_h)), "direction": direction}
            if counterparties:
                h["counterparty"] = self.r.choice(counterparties)
            if ttype:
                h["transaction_type"] = ttype
            out.append(h)
        return out

    def req(self, tx: Dict[str, Any], cust: Dict[str, Any], network=None, regime="US_BSA") -> Dict[str, Any]:
        tx.setdefault("timestamp", self.ts(0))
        tx.setdefault("currency", "USD")
        d = {"transaction": tx, "customer": cust, "regime": regime}
        if network:
            d["network_transactions"] = network
        return d


# ---------------------------------------------------------------------------
# Benign generators
# ---------------------------------------------------------------------------
def b_payroll(b: Builder, regime):
    name, employer = _person(b.r), _company(b.r) + " Payroll"
    amt = round(b.r.uniform(1500, 9000), 2)
    return b.req({"amount": amt, "transaction_type": "ACH", "direction": "IN", "origin_country": DOMESTIC[regime],
                  "destination_country": DOMESTIC[regime], "parties": [employer], "documents": ["Payroll register"]},
                 {"name": name, "customer_id": b.cid(), "account_age_days": b.r.randint(300, 4000),
                  "transaction_history": b.history(6, amt * .95, amt * 1.05, 24 * 170, counterparties=[employer], direction="IN")}, regime=regime)


def b_supplier(b: Builder, regime):
    co, sup = _company(b.r), _company(b.r)
    dest = b.r.choice(LEGIT_COUNTRIES)
    amt = round(b.r.uniform(3000, 180000), 2)
    return b.req({"amount": amt, "transaction_type": "WIRE_TRANSFER", "origin_country": DOMESTIC[regime], "destination_country": dest,
                  "parties": [co, sup], "documents": [f"Invoice INV-{b.r.randint(1000, 9999)}", "Purchase order"]},
                 {"name": co, "customer_id": b.cid(), "customer_type": "CORPORATE", "account_age_days": b.r.randint(400, 5000),
                  "transaction_history": b.history(b.r.randint(4, 9), amt * .6, amt * 1.4, 24 * 200, counterparties=[sup])}, regime=regime)


def b_retail(b: Builder, regime):
    name = _person(b.r)
    return b.req({"amount": round(b.r.uniform(20, 2500), 2), "transaction_type": "CARD", "origin_country": DOMESTIC[regime],
                  "destination_country": DOMESTIC[regime], "parties": [_company(b.r)]},
                 {"name": name, "customer_id": b.cid(), "account_age_days": b.r.randint(60, 3000),
                  "transaction_history": b.history(b.r.randint(2, 8), 15, 900, 24 * 20)}, regime=regime)


def b_remittance(b: Builder, regime):
    inr = regime == "IN_PMLA"
    amt = round(b.r.uniform(2000, 90000), 2) if inr else round(b.r.uniform(100, 2500), 2)
    name = _person(b.r)
    return b.req({"amount": amt, "currency": "INR" if inr else "USD", "transaction_type": "UPI" if inr else "WIRE_TRANSFER",
                  "origin_country": b.r.choice(["US", "GB", "AE", "SG"]) if not inr else "IN",
                  "destination_country": "IN", "parties": [_person(b.r)], "documents": []},
                 {"name": name, "customer_id": b.cid(), "account_age_days": b.r.randint(200, 2500),
                  "transaction_history": b.history(5, amt * .7, amt * 1.3, 24 * 150, currency="INR" if inr else "USD")}, regime=regime)


def b_real_estate(b: Builder, regime):
    amt = round(b.r.uniform(250000, 1_800_000), 2)
    return b.req({"amount": amt, "transaction_type": "WIRE_TRANSFER", "origin_country": DOMESTIC[regime], "destination_country": DOMESTIC[regime],
                  "parties": [_person(b.r), "Title and Escrow Services"], "documents": ["Sale agreement", "Title deed", "Mortgage statement"]},
                 {"name": _person(b.r), "customer_id": b.cid(), "account_age_days": b.r.randint(1500, 6000), "occupation": "Physician",
                  "transaction_history": b.history(8, 2000, 9000, 24 * 300)}, regime=regime)


def b_legit_offshore(b: Builder, regime):    # hard negative: secrecy-adjacent but fully documented, old account
    co = _company(b.r)
    dest = b.r.choice(["CH", "LU", "SG", "AE", "IE"])
    amt = round(b.r.uniform(20000, 350000), 2)
    return b.req({"amount": amt, "transaction_type": "WIRE_TRANSFER", "origin_country": DOMESTIC[regime], "destination_country": dest,
                  "parties": [co, _company(b.r)], "documents": ["Invoice", "Master services agreement", "Tax certificate"]},
                 {"name": co, "customer_id": b.cid(), "customer_type": "CORPORATE", "account_age_days": b.r.randint(900, 6000),
                  "transaction_history": b.history(8, amt * .5, amt * 1.3, 24 * 250)}, regime=regime)


def b_round_rent(b: Builder, regime):         # hard negative: round amounts
    amt = float(b.r.choice([12000, 15000, 20000, 25000, 30000, 50000]))
    landlord = _person(b.r)
    return b.req({"amount": amt, "transaction_type": "WIRE_TRANSFER", "origin_country": DOMESTIC[regime], "destination_country": DOMESTIC[regime],
                  "parties": [landlord], "documents": ["Lease agreement"]},
                 {"name": _company(b.r), "customer_id": b.cid(), "customer_type": "CORPORATE", "account_age_days": b.r.randint(500, 4000),
                  "transaction_history": [dict(amount=amt, timestamp=b.ts(24 * 30 * k), counterparty=landlord, direction="OUT") for k in range(1, 7)]}, regime=regime)


def b_busy_retailer(b: Builder, regime):      # hard negative: high velocity of small deposits
    co = _company(b.r) + " Store"
    return b.req({"amount": round(b.r.uniform(80, 900), 2), "transaction_type": "CARD", "direction": "IN", "origin_country": DOMESTIC[regime],
                  "destination_country": DOMESTIC[regime], "parties": ["Card acquirer"]},
                 {"name": co, "customer_id": b.cid(), "customer_type": "CORPORATE", "account_age_days": b.r.randint(500, 3000),
                  "transaction_history": b.history(b.r.randint(12, 20), 60, 800, 18, direction="IN")}, regime=regime)


def b_pep_lookalike(b: Builder, regime):      # hard negative: substring "king/gov/general" names that are NOT PEPs
    name = b.r.choice(["Kingston Freight Co", "Viking Logistics Ltd", "Governor's Bakery", "General Mills Distribution",
                       "Kingsley Brown", "Ambassador Hotel Group", "Kinglake Engineering"])
    return b.req({"amount": round(b.r.uniform(5000, 60000), 2), "transaction_type": "WIRE_TRANSFER", "origin_country": DOMESTIC[regime],
                  "destination_country": b.r.choice(["CA", "GB", "DE"]), "parties": [_company(b.r)], "documents": ["Invoice"]},
                 {"name": name, "customer_id": b.cid(), "customer_type": "CORPORATE", "account_age_days": b.r.randint(500, 3000),
                  "occupation": b.r.choice(["General Manager", "Vice President of Sales", "Director of Operations"]),
                  "transaction_history": b.history(5, 4000, 50000, 24 * 200)}, regime=regime)


def b_sanction_lookalike(b: Builder, regime):  # hard negative: shares a token with listed names
    party = b.r.choice(["Meridian Trading Co", "Russian Culinary Institute", "Vostok Travel Agency", "Tehran Carpet House",
                        "Black Anchor Pub", "Dragon Pearl Restaurant", "Crescent Medical Supplies", "Mirage Resort Ltd"])
    return b.req({"amount": round(b.r.uniform(2000, 40000), 2), "transaction_type": "WIRE_TRANSFER", "origin_country": DOMESTIC[regime],
                  "destination_country": b.r.choice(["GB", "AE", "SG", "CA"]), "parties": [party], "documents": ["Invoice"]},
                 {"name": _company(b.r), "customer_id": b.cid(), "customer_type": "CORPORATE", "account_age_days": b.r.randint(400, 3000),
                  "transaction_history": b.history(5, 2000, 40000, 24 * 200)}, regime=regime)


def b_legit_crypto(b: Builder, regime):
    amt = round(b.r.uniform(300, 40000), 2)
    return b.req({"amount": amt, "transaction_type": "CRYPTO", "asset_type": "CRYPTO", "origin_country": DOMESTIC[regime], "destination_country": DOMESTIC[regime],
                  "parties": ["Regulated Exchange"],
                  "crypto_details": {"wallet_age_days": b.r.randint(200, 1500), "mixer_used": False, "cross_chain_swaps": b.r.choice([0, 0, 1]), "token_type": "BTC"}},
                 {"name": _person(b.r), "customer_id": b.cid(), "account_age_days": b.r.randint(200, 2000),
                  "transaction_history": b.history(5, 300, 30000, 24 * 200)}, regime=regime)


def b_legit_trade(b: Builder, regime):
    value = round(b.r.uniform(30000, 400000), 2)
    co = _company(b.r)
    return b.req({"amount": value, "transaction_type": "TRADE_FINANCE", "origin_country": DOMESTIC[regime], "destination_country": b.r.choice(["SG", "JP", "DE", "AE"]),
                  "parties": [co, _company(b.r)], "documents": ["Commercial invoice", "Bill of lading", "Packing list"],
                  "trade_details": {"goods_description": b.r.choice(["Cotton yarn, 30s count", "Steel pipes, API 5L", "Frozen shrimp, 21/25 count"]),
                                    "invoice_value": value, "market_value_estimate": round(value * b.r.uniform(.92, 1.1), 2)}},
                 {"name": co, "customer_id": b.cid(), "customer_type": "CORPORATE", "account_age_days": b.r.randint(700, 5000),
                  "transaction_history": b.history(6, value * .4, value * 1.2, 24 * 250)}, regime=regime)



# --- messy-but-legitimate behaviour: realistic false-positive pressure ----------------
def b_cash_business(b: Builder, regime):       # restaurant/shop depositing near-threshold cash on a regular schedule
    inr = regime == "IN_PMLA"
    cur, thr = ("INR", 1_000_000) if inr else ("USD", 10_000)
    hist = [dict(amount=round(thr * b.r.uniform(.82, .99), 2), currency=cur, transaction_type="CASH",
                 timestamp=b.ts(24 * 2.5 * k + b.r.uniform(0, 8))) for k in range(1, b.r.randint(3, 5))]
    return b.req({"amount": round(thr * b.r.uniform(.84, .98), 2), "currency": cur, "transaction_type": "CASH", "origin_country": DOMESTIC[regime],
                  "destination_country": DOMESTIC[regime], "parties": [_company(b.r) + " Cafe"], "documents": ["Daily sales ledger"]},
                 {"name": _company(b.r) + " Cafe", "customer_id": b.cid(), "customer_type": "CORPORATE", "account_age_days": b.r.randint(500, 3500),
                  "occupation": "Restaurant owner", "transaction_history": hist}, regime=regime)


def b_startup_funding(b: Builder, regime):     # new company legitimately receiving a large investment round
    co = _company(b.r) + " Labs"
    return b.req({"amount": round(b.r.uniform(150000, 2_000_000), 2), "transaction_type": "WIRE_TRANSFER", "direction": "IN", "origin_country": b.r.choice(["US", "GB", "SG", "DE"]),
                  "destination_country": DOMESTIC[regime], "parties": [_company(b.r) + " Capital"], "documents": ["Term sheet", "Share subscription agreement"]},
                 {"name": co, "customer_id": b.cid(), "customer_type": "CORPORATE", "account_age_days": b.r.randint(8, 55), "transaction_history": []}, regime=regime)


def b_new_exchange_user(b: Builder, regime):   # newcomer buying/moving crypto on a regulated exchange
    return b.req({"amount": round(b.r.uniform(800, 35000), 2), "transaction_type": "CRYPTO", "asset_type": "CRYPTO", "origin_country": DOMESTIC[regime], "destination_country": DOMESTIC[regime],
                  "parties": ["Regulated Exchange"], "crypto_details": {"wallet_age_days": b.r.randint(1, 25), "mixer_used": False, "cross_chain_swaps": b.r.choice([0, 1, 2]), "token_type": "ETH"}},
                 {"name": _person(b.r), "customer_id": b.cid(), "account_age_days": b.r.randint(2, 40), "transaction_history": b.history(b.r.randint(0, 3), 200, 8000, 24 * 25)}, regime=regime)


def b_family_remittance(b: Builder, regime):   # larger family remittance to an elevated-risk corridor, no paperwork
    return b.req({"amount": round(b.r.uniform(12000, 70000), 2), "transaction_type": "WIRE_TRANSFER", "origin_country": DOMESTIC[regime], "destination_country": b.r.choice(["NP", "KE", "VN", "PK", "NG", "LB"]),
                  "parties": [_person(b.r)], "documents": b.r.choice([[], ["Beneficiary letter"]])},
                 {"name": _person(b.r), "customer_id": b.cid(), "account_age_days": b.r.randint(150, 3000), "transaction_history": b.history(4, 3000, 40000, 24 * 200)}, regime=regime)


def b_young_exporter(b: Builder, regime):      # young company, documented trade with a secrecy-adjacent hub
    value = round(b.r.uniform(20000, 220000), 2)
    co = _company(b.r)
    return b.req({"amount": value, "transaction_type": "WIRE_TRANSFER", "origin_country": DOMESTIC[regime], "destination_country": b.r.choice(["AE", "SG", "HK", "CH"]),
                  "parties": [co, _company(b.r)], "documents": ["Invoice", "Bill of lading"]},
                 {"name": co, "customer_id": b.cid(), "customer_type": "CORPORATE", "account_age_days": b.r.randint(60, 220), "transaction_history": b.history(3, value * .5, value, 24 * 50)}, regime=regime)


BENIGN: List[tuple] = [
    (b_payroll, .16, False), (b_supplier, .16, False), (b_retail, .12, False), (b_remittance, .08, False),
    (b_real_estate, .05, True), (b_legit_offshore, .08, True), (b_round_rent, .06, True), (b_busy_retailer, .06, True),
    (b_pep_lookalike, .04, True), (b_sanction_lookalike, .04, True), (b_legit_crypto, .04, True), (b_legit_trade, .05, True),
    (b_cash_business, .05, True), (b_startup_funding, .04, True), (b_new_exchange_user, .05, True), (b_family_remittance, .05, True),
    (b_young_exporter, .05, True),
]


# ---------------------------------------------------------------------------
# Suspicious generators
# ---------------------------------------------------------------------------
def s_structuring(b: Builder, regime):
    inr = regime == "IN_PMLA"
    cur, thr = ("INR", 1_000_000) if inr else ("USD", 10_000)
    k = b.r.randint(4, 6)
    hist = [dict(amount=round(thr * b.r.uniform(.90, .995), 2), currency=cur, transaction_type="CASH",
                 timestamp=b.ts(b.r.uniform(2, 24 * (20 if inr else 5)))) for _ in range(k)]
    return b.req({"amount": round(thr * b.r.uniform(.91, .99), 2), "currency": cur, "transaction_type": "CASH", "origin_country": DOMESTIC[regime],
                  "destination_country": DOMESTIC[regime], "parties": [_person(b.r)]},
                 {"name": _person(b.r), "customer_id": b.cid(), "account_age_days": b.r.randint(30, 900), "transaction_history": hist}, regime=regime), "structuring"


def s_sanctions_exact(b: Builder, regime):
    from sentinelai.engine.sanctions import get_screener
    entry = b.r.choice(get_screener().watchlist.entries)
    name = entry.name if b.r.random() < .6 else b.r.choice(entry.aliases or [entry.name])
    country = (entry.countries or ["RU"])[0]
    return b.req({"amount": round(b.r.uniform(15000, 900000), 2), "transaction_type": "WIRE_TRANSFER", "origin_country": b.r.choice(LEGIT_COUNTRIES),
                  "destination_country": country, "parties": [name, _company(b.r)], "documents": b.r.choice([[], ["Invoice"]])},
                 {"name": _company(b.r), "customer_id": b.cid(), "customer_type": "CORPORATE", "account_age_days": b.r.randint(100, 2000),
                  "transaction_history": []}, regime=regime), "sanctions"


def s_sanctions_fuzzy(b: Builder, regime):
    from sentinelai.engine.sanctions import get_screener
    from sentinelai.evaluation.variants import make_variant
    entry = b.r.choice(get_screener().watchlist.entries)
    variant = make_variant(entry.name, b.r.choice(["typo", "transposition", "reorder", "translit", "case_punct"]), b.r)
    return b.req({"amount": round(b.r.uniform(15000, 600000), 2), "transaction_type": "WIRE_TRANSFER", "origin_country": b.r.choice(LEGIT_COUNTRIES),
                  "destination_country": (entry.countries or ["AE"])[0], "parties": [variant], "documents": ["Invoice"]},
                 {"name": _company(b.r), "customer_id": b.cid(), "customer_type": "CORPORATE", "account_age_days": b.r.randint(100, 2000),
                  "transaction_history": []}, regime=regime), "sanctions"


def s_pep(b: Builder, regime):
    from sentinelai.engine.pep import get_pep_screener
    s = get_pep_screener()
    entry = b.r.choice(s.watchlist.entries)
    return b.req({"amount": round(b.r.uniform(250000, 4_000_000), 2), "transaction_type": "WIRE_TRANSFER", "origin_country": entry.countries[0] if entry.countries else "NG",
                  "destination_country": b.r.choice(["GB", "CH", "AE", "US"]), "parties": [_company(b.r) + " Trust"], "documents": ["Purchase agreement"]},
                 {"name": entry.name, "customer_id": b.cid(), "account_age_days": b.r.randint(5, 120), "nationality": entry.countries[0] if entry.countries else "NG",
                  "transaction_history": []}, regime=regime), "pep"


def s_tbml(b: Builder, regime):
    market = round(b.r.uniform(40000, 300000), 2)
    factor = b.r.choice([b.r.uniform(2.2, 4.0), b.r.uniform(.2, .5)])
    value = round(market * factor, 2)
    co = _company(b.r)
    return b.req({"amount": value, "transaction_type": "TRADE_FINANCE", "origin_country": b.r.choice(["HK", "AE", "CN", "PA", "TR"]), "destination_country": b.r.choice(["PA", "KY", "AE", "VG"]),
                  "parties": [co, _company(b.r)], "documents": b.r.choice([["Commercial invoice"], []]),
                  "trade_details": {"goods_description": b.r.choice(["Used mobile phones", "General goods", "Electronic components", "Miscellaneous"]),
                                    "invoice_value": value, "market_value_estimate": market}},
                 {"name": co, "customer_id": b.cid(), "customer_type": "CORPORATE", "account_age_days": b.r.randint(30, 400), "transaction_history": []}, regime=regime), "tbml"


def s_crypto(b: Builder, regime):
    d = {"wallet_age_days": b.r.randint(0, 20), "mixer_used": b.r.random() < .7, "cross_chain_swaps": b.r.randint(2, 7),
         "privacy_coin": b.r.random() < .4}
    if b.r.random() < .4:
        d["darknet_market"] = b.r.choice(["hydra_remnant", "alphabay clone", "world market"])
    return b.req({"amount": round(b.r.uniform(20000, 600000), 2), "transaction_type": "CRYPTO", "asset_type": "CRYPTO", "origin_country": "US", "destination_country": "US",
                  "parties": ["unhosted_wallet"], "crypto_details": d},
                 {"name": _person(b.r), "customer_id": b.cid(), "account_age_days": b.r.randint(2, 60), "transaction_history": []}, regime=regime), "crypto"


def s_round_trip(b: Builder, regime):
    me, hops = _company(b.r) + " Ventures", b.r.randint(1, 3)
    chain = [me] + [_company(b.r) + " Holdings" for _ in range(hops)]
    amt = round(b.r.uniform(60000, 500000), 2)
    net, t = [], 96
    for i in range(1, len(chain)):
        net.append({"sender": chain[i - 1], "receiver": chain[i], "amount": round(amt * b.r.uniform(.96, 1.0), 2), "timestamp": b.ts(t)})
        t -= 24 / hops
    last = chain[-1]
    if hops == 1:   # 2-cycle: customer paid out earlier, now money returns
        hist = [dict(amount=round(amt, 2), counterparty=last, direction="OUT", timestamp=b.ts(72))]
        net = []
    else:
        hist = []
        net = net  # path me->...->last in network, then last->me is the current tx
    return b.req({"amount": round(amt * .97, 2), "transaction_type": "WIRE_TRANSFER", "origin_country": "US", "destination_country": "US", "parties": [me, last],
                  "sender_account": last, "receiver_account": me, "documents": ["Consulting agreement"]},
                 {"name": me, "customer_id": me, "customer_type": "CORPORATE", "account_age_days": b.r.randint(200, 1500), "transaction_history": hist},
                 network=net, regime=regime), "round_trip"


def s_mule(b: Builder, regime):
    me = _company(b.r) + " Consulting"
    k = b.r.randint(5, 9)
    amt = b.r.uniform(900, 2500)
    hist = [dict(amount=round(amt * b.r.uniform(.9, 1.1), 2), counterparty=f"{_person(b.r)} {i}", direction="IN", timestamp=b.ts(b.r.uniform(6, 30))) for i in range(k)]
    total = sum(h["amount"] for h in hist)
    return b.req({"amount": round(total * .96, 2), "transaction_type": "WIRE_TRANSFER", "origin_country": DOMESTIC[regime],
                  "destination_country": b.r.choice(["VG", "KY", "PA", "SC", "BZ"]), "parties": [me, _company(b.r) + " Capital"],
                  "sender_account": me, "receiver_account": _company(b.r) + " Capital", "documents": []},
                 {"name": me, "customer_id": me, "customer_type": "CORPORATE", "account_age_days": b.r.randint(5, 60), "transaction_history": hist}, regime=regime), "mule_fan_in"


def s_layering(b: Builder, regime):
    co = _company(b.r)
    return b.req({"amount": round(b.r.uniform(120000, 2_000_000), 2), "transaction_type": "WIRE_TRANSFER", "origin_country": b.r.choice(["RU", "IR", "BY", "VE", "SY", "MM"]),
                  "destination_country": b.r.choice(["KY", "VG", "PA", "SC", "BM"]), "intermediate_countries": b.r.sample(["AE", "CH", "TR", "HK", "CY", "MT"], 2),
                  "parties": [co, _company(b.r) + " Holdings"], "documents": []},
                 {"name": co, "customer_id": b.cid(), "customer_type": "CORPORATE", "account_age_days": b.r.randint(10, 120), "transaction_history": []}, regime=regime), "layering"


def s_new_account(b: Builder, regime):
    co = _company(b.r)
    return b.req({"amount": round(b.r.uniform(60000, 800000), 2), "transaction_type": "WIRE_TRANSFER", "origin_country": DOMESTIC[regime],
                  "destination_country": b.r.choice(["PA", "KY", "SC", "MU", "VG", "LA", "KE"]), "parties": [co, _company(b.r)], "documents": []},
                 {"name": co, "customer_id": b.cid(), "customer_type": "CORPORATE", "account_age_days": b.r.randint(1, 25),
                  "transaction_history": b.history(b.r.randint(3, 6), 8000, 60000, 24 * 8)}, regime=regime), "new_account_abuse"



# --- stealth variants: weaker, partial evidence (the cases that actually test a detector) ------------
def s_structuring_stealth(b: Builder, regime):
    inr = regime == "IN_PMLA"
    cur, thr = ("INR", 1_000_000) if inr else ("USD", 10_000)
    hist = [dict(amount=round(thr * b.r.uniform(.85, .99), 2), currency=cur, transaction_type="CASH",
                 timestamp=b.ts(b.r.uniform(30, 24 * (25 if inr else 8)))) for _ in range(b.r.randint(1, 2))]
    return b.req({"amount": round(thr * b.r.uniform(.88, .99), 2), "currency": cur, "transaction_type": "CASH", "origin_country": DOMESTIC[regime],
                  "destination_country": DOMESTIC[regime], "parties": [_person(b.r)]},
                 {"name": _person(b.r), "customer_id": b.cid(), "account_age_days": b.r.randint(20, 400), "transaction_history": hist}, regime=regime), "structuring"


def s_tbml_stealth(b: Builder, regime):
    market = round(b.r.uniform(40000, 300000), 2)
    value = round(market * b.r.choice([b.r.uniform(1.3, 1.6), b.r.uniform(.55, .75)]), 2)
    co = _company(b.r)
    return b.req({"amount": value, "transaction_type": "TRADE_FINANCE", "origin_country": DOMESTIC[regime], "destination_country": b.r.choice(["SG", "AE", "HK", "TR"]),
                  "parties": [co, _company(b.r)], "documents": ["Commercial invoice", "Bill of lading"],
                  "trade_details": {"goods_description": "Electronic components", "invoice_value": value, "market_value_estimate": market}},
                 {"name": co, "customer_id": b.cid(), "customer_type": "CORPORATE", "account_age_days": b.r.randint(150, 900), "transaction_history": b.history(3, 20000, value, 24 * 120)}, regime=regime), "tbml"


def s_mule_stealth(b: Builder, regime):
    me = _company(b.r) + " Services"
    k = b.r.randint(3, 4)
    amt = b.r.uniform(1500, 4500)
    hist = [dict(amount=round(amt * b.r.uniform(.9, 1.1), 2), counterparty=f"{_person(b.r)} {i}", direction="IN", timestamp=b.ts(b.r.uniform(10, 50))) for i in range(k)]
    total = sum(h["amount"] for h in hist)
    return b.req({"amount": round(total * b.r.uniform(.75, .9), 2), "transaction_type": "WIRE_TRANSFER", "origin_country": DOMESTIC[regime],
                  "destination_country": b.r.choice(["AE", "TR", "CY", "VG"]), "parties": [me, _company(b.r)], "sender_account": me,
                  "receiver_account": _company(b.r), "documents": []},
                 {"name": me, "customer_id": me, "customer_type": "CORPORATE", "account_age_days": b.r.randint(20, 120), "transaction_history": hist}, regime=regime), "mule_fan_in"


def s_pep_stealth(b: Builder, regime):
    return b.req({"amount": round(b.r.uniform(80000, 400000), 2), "transaction_type": "WIRE_TRANSFER", "origin_country": DOMESTIC[regime],
                  "destination_country": b.r.choice(["GB", "AE", "CH", "SG"]), "parties": [_company(b.r)], "documents": ["Sale agreement"]},
                 {"name": _person(b.r), "customer_id": b.cid(), "account_age_days": b.r.randint(100, 1500),
                  "occupation": b.r.choice(["Deputy Minister of Mining", "Member of Parliament", "State Governor", "Ambassador to the UN"]),
                  "transaction_history": b.history(4, 5000, 60000, 24 * 200)}, regime=regime), "pep"


def s_layering_stealth(b: Builder, regime):
    co = _company(b.r)
    return b.req({"amount": round(b.r.uniform(60000, 400000), 2), "transaction_type": "WIRE_TRANSFER", "origin_country": DOMESTIC[regime],
                  "destination_country": b.r.choice(["VE", "MM", "IR", "KP", "SY", "BY"]), "parties": [co, _company(b.r)], "documents": ["Contract"]},
                 {"name": co, "customer_id": b.cid(), "customer_type": "CORPORATE", "account_age_days": b.r.randint(100, 600), "transaction_history": b.history(3, 20000, 100000, 24 * 150)}, regime=regime), "layering"


def s_sanctions_stealth(b: Builder, regime):
    from sentinelai.engine.sanctions import get_screener
    from sentinelai.evaluation.variants import make_variant
    entry = b.r.choice(get_screener().watchlist.entries)
    variant = make_variant(entry.name, b.r.choice(["extra_token", "drop_token", "translit"]), b.r)
    return b.req({"amount": round(b.r.uniform(20000, 300000), 2), "transaction_type": "WIRE_TRANSFER", "origin_country": DOMESTIC[regime], "destination_country": b.r.choice(["GB", "DE", "SG", "TR"]),
                  "parties": [variant], "documents": ["Invoice"]},
                 {"name": _company(b.r), "customer_id": b.cid(), "customer_type": "CORPORATE", "account_age_days": b.r.randint(200, 2000), "transaction_history": []}, regime=regime), "sanctions"


def s_crypto_stealth(b: Builder, regime):
    return b.req({"amount": round(b.r.uniform(5000, 45000), 2), "transaction_type": "CRYPTO", "asset_type": "CRYPTO", "origin_country": DOMESTIC[regime], "destination_country": DOMESTIC[regime],
                  "parties": ["unhosted_wallet"], "crypto_details": {"wallet_age_days": b.r.randint(60, 400), "mixer_used": True, "cross_chain_swaps": b.r.randint(0, 2)}},
                 {"name": _person(b.r), "customer_id": b.cid(), "account_age_days": b.r.randint(100, 900), "transaction_history": b.history(4, 1000, 20000, 24 * 150)}, regime=regime), "crypto"


def s_new_account_stealth(b: Builder, regime):
    co = _company(b.r)
    return b.req({"amount": round(b.r.uniform(15000, 60000), 2), "transaction_type": "WIRE_TRANSFER", "origin_country": DOMESTIC[regime],
                  "destination_country": b.r.choice(["PA", "SC", "KY", "BZ"]), "parties": [co, _company(b.r)], "documents": ["Invoice"]},
                 {"name": co, "customer_id": b.cid(), "customer_type": "CORPORATE", "account_age_days": b.r.randint(15, 29), "transaction_history": b.history(2, 3000, 15000, 24 * 15)}, regime=regime), "new_account_abuse"


def s_round_trip_stealth(b: Builder, regime):
    me = _company(b.r) + " Partners"
    chain = [me] + [_company(b.r) + " Trading" for _ in range(4)]
    amt = round(b.r.uniform(60000, 400000), 2)
    net, t = [], 200
    for i in range(1, len(chain)):
        net.append({"sender": chain[i - 1], "receiver": chain[i], "amount": round(amt * b.r.uniform(.8, .95), 2), "timestamp": b.ts(t)})
        t -= 40
    return b.req({"amount": round(amt * b.r.uniform(.7, .85), 2), "transaction_type": "WIRE_TRANSFER", "origin_country": "US", "destination_country": "US", "parties": [me, chain[-1]],
                  "sender_account": chain[-1], "receiver_account": me, "documents": ["Services agreement"]},
                 {"name": me, "customer_id": me, "customer_type": "CORPORATE", "account_age_days": b.r.randint(200, 1500), "transaction_history": []}, network=net, regime=regime), "round_trip"


STEALTH = [s_structuring_stealth, s_tbml_stealth, s_mule_stealth, s_pep_stealth, s_layering_stealth, s_sanctions_stealth,
           s_crypto_stealth, s_new_account_stealth, s_round_trip_stealth]


SUSPICIOUS = [s_structuring, s_sanctions_exact, s_sanctions_fuzzy, s_pep, s_tbml, s_crypto, s_round_trip, s_mule, s_layering, s_new_account]


def make_dataset(n: int = 1000, seed: int = 7, suspicious_ratio: float = 0.2, regime: str = "US_BSA",
                 now: Optional[datetime] = None, stealth_fraction: float = 0.45) -> List[Sample]:
    now = now or datetime(2026, 10, 1, 12, 0, tzinfo=timezone.utc)
    b = Builder(seed, now)
    r = b.r
    samples: List[Sample] = []
    n_sus = int(round(n * suspicious_ratio))
    for i in range(n - n_sus):
        fn, _, hard = r.choices(BENIGN, weights=[w for _, w, _ in BENIGN])[0]
        samples.append(Sample(f"B{i:05d}", fn(b, regime), 0, None, hard))
    n_stealth = int(round(n_sus * stealth_fraction))
    for i in range(n_sus):
        fn = STEALTH[i % len(STEALTH)] if i < n_stealth else SUSPICIOUS[i % len(SUSPICIOUS)]
        req, typology = fn(b, regime)
        samples.append(Sample(f"S{i:05d}", req, 1, typology, hard_negative=False))
    r.shuffle(samples)
    return samples
