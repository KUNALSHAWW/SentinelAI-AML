"""Small units: time, fx, regimes, jurisdictions, cache, scenarios, reporting."""

from datetime import datetime, timedelta, timezone

import pytest

from sentinelai.core import fx
from sentinelai.core.cache import MemoryCache
from sentinelai.core.jurisdictions import CALL_FOR_ACTION, OFFSHORE_SECRECY, get_jurisdictions
from sentinelai.core.regimes import REGIMES, get_regime
from sentinelai.core.time import ensure_utc, utcnow
from sentinelai.services.scenarios import load_scenarios, scenario_request


def test_ensure_utc_variants():
    assert ensure_utc("2026-01-01T10:00:00Z") == datetime(2026, 1, 1, 10, tzinfo=timezone.utc)
    assert ensure_utc("2026-01-01T10:00:00+05:30") == datetime(2026, 1, 1, 4, 30, tzinfo=timezone.utc)
    assert ensure_utc(datetime(2026, 1, 1)).tzinfo == timezone.utc
    assert ensure_utc("garbage") is None and ensure_utc(None, utcnow()) is not None and ensure_utc(5) is None


def test_fx_conversion_and_unknown_currency():
    assert fx.to_usd(100, "USD") == 100 and fx.to_usd(100, "EUR") > 100
    assert fx.to_usd(100, "ZZZ") == 100                       # unknown: never crash
    assert fx.convert(1_000_000, "INR", "USD") == pytest.approx(11_300)
    assert fx.convert(11_300, "USD", "INR") == pytest.approx(1_000_000, rel=1e-3)


def test_fx_override(monkeypatch):
    from sentinelai.core.config import settings
    monkeypatch.setattr(settings.risk, "fx_rates", {"inr": 0.02})
    assert fx.to_usd(1000, "INR") == pytest.approx(20)


def test_regime_profiles_match_researched_rules():
    us, india, eu = (get_regime(c) for c in ("US_BSA", "IN_PMLA", "EU_AMLD"))
    assert us.cash_report_threshold == 10_000 and us.filing_days == 30 and us.suspicious_report == "SAR"
    assert india.cash_report_threshold == 1_000_000 and india.filing_days == 7 and india.working_days and india.suspicious_report == "STR"
    assert eu.filing_days is None and eu.filing_deadline() is None
    with pytest.raises(ValueError):
        get_regime("MARS")


def test_working_day_deadline_skips_weekends():
    friday = datetime(2026, 10, 2, 9, tzinfo=timezone.utc)
    assert friday.weekday() == 4
    due = REGIMES["IN_PMLA"].filing_deadline(friday)
    assert due.weekday() < 5 and (due - friday).days == 11          # Fri + 7 working days = Tue of week two
    assert REGIMES["US_BSA"].filing_deadline(friday) == friday + timedelta(days=30)


def test_jurisdiction_data():
    j = get_jurisdictions()
    assert j.as_of >= "2026-06-19"
    assert {"IR", "KP", "MM"} == set(j.call_for_action)
    assert len(j.increased_monitoring) == 22 and {"BA", "IQ", "KW", "VG"} <= set(j.increased_monitoring)
    assert "DZ" not in j.increased_monitoring and "NA" not in j.increased_monitoring        # removed in June 2026
    assert j.categories("IRN") == [CALL_FOR_ACTION, "SANCTIONS_EXPOSURE"] and j.categories("ky") == [OFFSHORE_SECRECY]
    assert j.categories("US") == [] and j.normalize("  rus ") == "RU" and j.normalize(None) == "" and j.name("RU") == "Russia"


async def test_memory_cache_ttl_incr_and_bound():
    c = MemoryCache(max_items=3)
    await c.set("a", "1", ttl=60)
    assert await c.get("a") == "1" and await c.get("missing") is None
    await c.set("gone", "x", ttl=-1)
    assert await c.get("gone") is None
    assert [await c.incr("k", 60) for _ in range(3)] == [1, 2, 3]
    for i in range(10):
        await c.set(f"f{i}", "x", 60)
    assert len(c._data) <= 3


def test_scenarios_resolve_relative_timestamps_freshly():
    now = datetime(2026, 5, 1, tzinfo=timezone.utc)
    s = {x["id"]: x for x in load_scenarios(now)}
    assert len(s) >= 12 and "ts_offset_hours" not in str(s)
    tx_ts = datetime.fromisoformat(s["structuring-us"]["transaction"]["timestamp"])
    assert tx_ts == now
    hist = [datetime.fromisoformat(h["timestamp"]) for h in s["structuring-us"]["customer"]["transaction_history"]]
    assert all(h < now for h in hist)
    assert "network_transactions" in scenario_request(s["round-trip"]) and scenario_request(s["structuring-india"])["regime"] == "IN_PMLA"


def test_bundled_scenarios_have_expected_outcomes(engine):
    """Golden behaviour of each demo scenario (also the frontend's one-click demos)."""
    from sentinelai.engine import build_input
    expect = {"clean": "LOW", "low-risk": "LOW", "sanctions-hit": "CRITICAL", "crypto-mixer": "CRITICAL", "round-trip": "CRITICAL",
              "structuring-us": "HIGH", "structuring-india": "HIGH", "offshore-routing": "HIGH", "mule-fan-in": "CRITICAL"}
    for sc in load_scenarios():
        r = scenario_request(sc)
        res = engine.run(build_input(r["transaction"], r["customer"], r.get("network_transactions"), regime=r.get("regime")))
        if sc["id"] in expect:
            assert res.score.level == expect[sc["id"]], (sc["id"], res.score.score)
    sanc = next(s for s in load_scenarios() if s["id"] == "sanctions-fuzzy")
    r = scenario_request(sanc)
    res = engine.run(build_input(r["transaction"], r["customer"]))
    assert not res.decision["sanctions_confirmed"] and any(s.code.startswith("SANCTIONS_") for s in res.signals)


def test_report_structure_and_markdown(engine, make_ctx):
    from sentinelai.services import reporting
    res = engine.run(make_ctx(tx={"parties": ["Sanctioned Russian Bank"], "amount": 900_000}))
    rep = reporting.build_report(res, res.score, res.decision, res.signals, case_number="CASE-1")
    assert rep["status"].startswith("DRAFT") and rep["report_type"] == "SAR" and rep["filing_deadline"]
    assert set(rep["narrative"]["body"]) == {"who", "what", "when", "where", "why", "how"}
    assert "Sanctioned Russian Bank" in rep["narrative_text"] and rep["limitations"]
    md = reporting.to_markdown(rep)
    assert md.startswith("# SAR draft - CASE-1") and "## Red flags" in md
