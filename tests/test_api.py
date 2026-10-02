"""HTTP API behaviour."""

import json
import uuid

import pytest

from tests.conftest import ts

TX = {"amount": 5000, "currency": "USD", "transaction_type": "WIRE_TRANSFER", "origin_country": "US", "destination_country": "CA",
      "parties": ["Acme Supplies"], "documents": ["Invoice"]}
CUST = {"name": "Jane Roe", "customer_id": "c-jane", "customer_type": "INDIVIDUAL", "account_age_days": 800}


def payload(tx=None, cust=None, **extra):
    return {"transaction": {**TX, **(tx or {})}, "customer": {**CUST, **(cust or {})}, "enable_llm_analysis": False, **extra}


# ------------------------------------------------------------------ system
def test_health_reports_real_dependencies(client):
    d = client.get("/health").json()
    assert d["status"] == "healthy"
    deps = d["dependencies"]
    assert deps["database"]["status"] == "connected" and deps["sanctions_list"]["synthetic_demo_data"] is True
    assert deps["web_search"].startswith("disabled") and deps["llm"]["configured"] is False


def test_root_serves_frontend_and_api_root_serves_json(client):
    r = client.get("/")
    assert r.status_code == 200 and "text/html" in r.headers["content-type"]
    assert client.get("/api").json()["name"] == "SentinelAI"


def test_metrics_endpoint_exposes_prometheus_counters(client):
    client.post("/api/v1/analyze", json=payload())
    body = client.get("/metrics").text
    assert "sentinelai_analyses_total" in body and "sentinelai_http_requests_total" in body


def test_reference_endpoints(client):
    j = client.get("/api/v1/reference/jurisdictions").json()
    assert "IR" in j["fatf_call_for_action"] and j["as_of"]
    assert {r["code"] for r in client.get("/api/v1/reference/regimes").json()["regimes"]} == {"US_BSA", "IN_PMLA", "EU_AMLD"}
    assert "ROUND_TRIPPING" in client.get("/api/v1/reference/typologies").json()
    scenarios = client.get("/api/v1/reference/scenarios").json()
    assert len(scenarios) >= 10 and all("request" in s for s in scenarios)
    assert client.get("/api/v1/reference/screening-lists").json()["sanctions"]["synthetic"] is True


# ------------------------------------------------------------------ analysis
def test_analyze_response_contract(client):
    d = client.post("/api/v1/analyze", json=payload()).json()
    for key in ("risk_assessment", "explanation", "typologies", "screening", "graph", "mode", "llm_status", "warnings", "audit",
                "recommended_action", "next_steps", "sar_required", "regime", "analysis_id"):
        assert key in d, key
    ra = d["risk_assessment"]
    assert ra["risk_level"] == "LOW" and d["mode"] == "deterministic" and d["llm_status"] == "disabled"
    assert any("DEMO" in w for w in d["warnings"])


def test_explanation_sums_to_score_and_audit_is_chained(client):
    d = client.post("/api/v1/analyze", json=payload(tx={"origin_country": "RU", "destination_country": "KY", "amount": 600000, "documents": []})).json()
    assert sum(c["points"] for c in d["explanation"]["contributions"]) == d["risk_assessment"]["risk_score"]
    assert d["audit"]["seq"] >= 1 and len(d["audit"]["entry_hash"]) == 64
    assert client.get("/api/v1/audit/verify").json()["valid"] is True


def test_sanctions_hit_creates_case_alerts_and_report(client):
    d = client.post("/api/v1/analyze", json=payload(tx={"parties": ["Sanctioned Russian Bank"], "amount": 2_000_000})).json()
    assert d["recommended_action"] == "BLOCK" and d["risk_assessment"]["risk_score"] >= 95 and d["sar_required"]
    assert d["case"]["case_number"].startswith("CASE-") and d["case"]["status"] == "OPEN"
    assert d["report"]["report_type"] == "SAR" and d["report"]["case_number"] == d["case"]["case_number"]
    assert "SANCTIONS_HIT" in d["risk_assessment"]["alerts_triggered"] and d["alerts"]
    md = client.get(f"/api/v1/cases/{d['case']['id']}/report", params={"format": "markdown"})
    assert md.status_code == 200 and md.text.startswith("# SAR draft")
    stored = client.get(f"/api/v1/cases/{d['case']['id']}").json()
    assert stored["analysis_id"] == d["analysis_id"]


def test_analysis_is_retrievable_and_listed(client):
    d = client.post("/api/v1/analyze", json=payload()).json()
    got = client.get(f"/api/v1/analyses/{d['analysis_id']}").json()
    assert got["analysis_id"] == d["analysis_id"] and got["risk_assessment"]["risk_score"] == d["risk_assessment"]["risk_score"]
    assert client.get("/api/v1/analyses").json()[0]["analysis_id"] == d["analysis_id"]
    assert client.get(f"/api/v1/analyses/{uuid.uuid4()}").status_code == 404


def test_rules_endpoint_matches_analyze_with_llm_disabled(client):
    a = client.post("/api/v1/analyze/rules", json={**payload(), "enable_llm_analysis": True}).json()
    b = client.post("/api/v1/analyze", json=payload()).json()
    assert a["risk_assessment"]["risk_score"] == b["risk_assessment"]["risk_score"] and a["mode"] == "deterministic"


def test_request_llm_without_key_is_reported_not_silent(client):
    d = client.post("/api/v1/analyze", json={**payload(), "enable_llm_analysis": True}).json()
    assert d["llm_status"] == "no_api_key" and any("API key" in w for w in d["warnings"])


def test_regime_changes_report_and_deadline(client):
    d = client.post("/api/v1/analyze", json=payload(
        tx={"amount": 950_000, "currency": "INR", "transaction_type": "CASH", "origin_country": "IN", "destination_country": "IN", "documents": []},
        cust={"transaction_history": [{"amount": a, "currency": "INR", "timestamp": ts(h), "transaction_type": "CASH"} for a, h in [(920_000, 20), (980_000, 100), (940_000, 300)]]},
        regime="IN_PMLA")).json()
    assert d["regime"]["code"] == "IN_PMLA" and d["report"]["report_type"] == "STR" and "BEH_STRUCTURING_PATTERN" in {f["code"] for f in d["risk_assessment"]["risk_factors"]}


def test_persist_false_stores_nothing(client):
    d = client.post("/api/v1/analyze", json=payload(tx={"parties": ["Sanctioned Russian Bank"]}, persist=False)).json()
    assert d["analysis_id"] is None and d["case"] is None and d["audit"] is None and d["alerts"]
    assert client.get("/api/v1/cases").json() == []


def test_confidential_flag_never_changes_deterministic_score(client):
    a = client.post("/api/v1/analyze", json=payload()).json()["risk_assessment"]["risk_score"]
    b = client.post("/api/v1/analyze", json=payload(restrict_external_lookup=True)).json()["risk_assessment"]["risk_score"]
    assert a == b


@pytest.mark.parametrize("bad", [
    {"transaction": {"currency": "USD"}, "customer": {"name": "x"}},
    {"transaction": {**TX, "amount": -5}, "customer": CUST},
    {"transaction": {**TX, "amount": 0}, "customer": CUST},
    {"transaction": TX, "customer": {"name": ""}},
    {"transaction": {**TX, "transaction_type": "TELEPORT"}, "customer": CUST},
])
def test_validation_errors_are_422(client, bad):
    assert client.post("/api/v1/analyze", json=bad).status_code == 422


def test_batch_reports_failures_instead_of_dropping(client, monkeypatch):
    from sentinelai.api import deps
    svc = deps.get_analysis_service()
    real = svc.analyze_transaction
    calls = {"n": 0}

    async def flaky(req, principal=None, progress_callback=None):
        calls["n"] += 1
        if req.customer.name == "Boom":
            raise RuntimeError("secret internal detail")
        return await real(req, principal)
    monkeypatch.setattr(svc, "analyze_transaction", flaky)
    body = {"transactions": [payload(), payload(cust={"name": "Boom"}), payload()]}
    d = client.post("/api/v1/analyze/batch", json=body).json()
    assert (d["total"], d["succeeded"], d["failed"]) == (3, 2, 1)
    bad = d["items"][1]
    assert bad["index"] == 1 and bad["status"] == "error" and "secret" not in json.dumps(bad)


def test_sse_stream_emits_progress_then_result(client):
    with client.stream("POST", "/api/v1/analyze/stream", json=payload()) as r:
        events = [json.loads(line[6:]) for line in r.iter_lines() if line.startswith("data: ")]
    types = [e["type"] for e in events]
    assert types[-1] == "result" and "progress" in types
    assert events[-1]["result"]["risk_assessment"]["risk_level"] == "LOW"


def test_unhandled_errors_do_not_leak_internals(client_soft, monkeypatch):
    client = client_soft
    from sentinelai.api import deps
    svc = deps.get_analysis_service()

    async def explode(*a, **k):
        raise RuntimeError("password=hunter2 stack detail")
    monkeypatch.setattr(svc, "analyze_transaction", explode)
    r = client.post("/api/v1/analyze", json=payload())
    assert r.status_code == 500 and "hunter2" not in r.text and r.json()["details"]["error_id"]


def test_request_id_roundtrip_and_rate_headers(client):
    r = client.get("/health", headers={"X-Request-ID": "abc-123"})
    assert r.headers["X-Request-ID"] == "abc-123"
    assert client.get("/health", headers={"X-Request-ID": "bad id with spaces<script>"}).headers["X-Request-ID"] != "bad id with spaces<script>"


def test_graph_memory_across_analyses_detects_cross_request_round_trip(client):
    """Each request alone is innocuous; the persisted graph links them into a cycle."""
    def hop(a, b, hours_ago, amt):
        return payload(tx={"amount": amt, "parties": [a, b], "sender_account": a, "receiver_account": b, "timestamp": ts(hours_ago)},
                       cust={"name": a, "customer_id": a})
    for a, b, h, amt in [("Alpha Co", "Beta Co", 60, 90_000), ("Beta Co", "Gamma Co", 40, 89_000)]:
        r = client.post("/api/v1/analyze", json=hop(a, b, h, amt)).json()
        assert "NET_ROUND_TRIP" not in {f["code"] for f in r["risk_assessment"]["risk_factors"]}
    closing = client.post("/api/v1/analyze", json=hop("Gamma Co", "Alpha Co", 10, 88_000)).json()
    assert "NET_ROUND_TRIP" in {f["code"] for f in closing["risk_assessment"]["risk_factors"]}
    assert any(h["type"] == "cycle" and h["length"] == 3 for h in closing["graph"]["highlights"])


def test_graph_memory_is_not_used_when_not_persisting(client):
    for a, b, h in [("Alpha Co", "Beta Co", 60), ("Beta Co", "Gamma Co", 40)]:
        client.post("/api/v1/analyze", json=payload(tx={"amount": 90_000, "parties": [a, b], "sender_account": a, "receiver_account": b, "timestamp": ts(h)}, cust={"name": a, "customer_id": a}))
    r = client.post("/api/v1/analyze", json=payload(tx={"amount": 88_000, "parties": ["Gamma Co", "Alpha Co"], "sender_account": "Gamma Co", "receiver_account": "Alpha Co", "timestamp": ts(10)},
                                                     cust={"name": "Gamma Co", "customer_id": "Gamma Co"}, persist=False)).json()
    assert "NET_ROUND_TRIP" not in {f["code"] for f in r["risk_assessment"]["risk_factors"]}


# ------------------------------------------------------------------ cases over HTTP
def test_case_endpoints_enforce_state_machine(client):
    c = client.post("/api/v1/cases", json={"title": "Manual", "priority": "HIGH"}).json()
    cid = c["id"]
    assert client.patch(f"/api/v1/cases/{cid}", json={"status": "UNDER_REVIEW"}).json()["status"] == "UNDER_REVIEW"
    assert client.post(f"/api/v1/cases/{cid}/sar", params={"sar_reference": "R-1"}).json()["sar_filed"] is True
    r = client.patch(f"/api/v1/cases/{cid}", json={"status": "OPEN"})
    assert r.status_code == 409
    assert client.get(f"/api/v1/cases/{uuid.uuid4()}").status_code == 404
    assert client.post(f"/api/v1/cases/{cid}/comments", json={"content": "note"}).status_code == 200
    assert len(client.get(f"/api/v1/cases/{cid}/comments").json()) >= 2


def test_alert_listing_and_triage(client):
    client.post("/api/v1/analyze", json=payload(tx={"parties": ["Sanctioned Russian Bank"]}))
    alerts = client.get("/api/v1/alerts", params={"status": "OPEN"}).json()
    assert alerts and alerts[0]["alert_type"]
    done = client.patch(f"/api/v1/alerts/{alerts[0]['id']}", params={"status": "FALSE_POSITIVE"}).json()
    assert done["status"] == "FALSE_POSITIVE"
    assert client.get("/api/v1/alerts", params={"status": "bogus"}).status_code == 422


def test_dashboard_reflects_activity(client):
    client.post("/api/v1/analyze", json=payload(tx={"parties": ["Sanctioned Russian Bank"]}))
    m = client.get("/api/v1/dashboard/metrics").json()
    assert m["total_transactions_24h"] == 1 and m["suspicious_transactions_24h"] == 1 and m["open_cases"] == 1


def test_frontend_dir_resolution(tmp_path, monkeypatch):
    from sentinelai.api.app import resolve_frontend_dir
    (tmp_path / "ui").mkdir()
    (tmp_path / "ui" / "index.html").write_text("<html>custom</html>")
    monkeypatch.setenv("SENTINEL_FRONTEND_DIR", str(tmp_path / "ui"))
    assert resolve_frontend_dir() == tmp_path / "ui"
    monkeypatch.delenv("SENTINEL_FRONTEND_DIR")
    (tmp_path / "frontend").mkdir()
    (tmp_path / "frontend" / "index.html").write_text("x")
    monkeypatch.chdir(tmp_path)
    assert resolve_frontend_dir() == tmp_path / "frontend"          # the Docker case: package installed elsewhere, cwd=/app


def test_request_priority_raises_case_priority_but_never_lowers_it(client):
    sanc = payload(tx={"parties": ["Sanctioned Russian Bank"]}, priority="LOW")
    assert client.post("/api/v1/analyze", json=sanc).json()["case"]["priority"] == "CRITICAL"       # engine says critical
    structuring = payload(tx={"amount": 9500, "transaction_type": "CASH", "origin_country": "US", "destination_country": "US"},
                          cust={"transaction_history": [{"amount": a, "timestamp": ts(h), "transaction_type": "CASH"} for a, h in [(9200, 8), (9800, 30), (9600, 52)]]},
                          priority="CRITICAL")
    d = client.post("/api/v1/analyze", json=structuring).json()
    assert d["case"]["priority"] == "CRITICAL" and d["risk_assessment"]["risk_level"] == "HIGH"
