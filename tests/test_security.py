"""Authentication, RBAC, rate limiting and CORS."""

import pytest

from sentinelai.core import security
from sentinelai.core.config import settings
from tests.test_api import payload

ADMIN, ANALYST, VIEWER = {"X-API-Key": "adminkey"}, {"X-API-Key": "analystkey"}, {"X-API-Key": "viewerkey"}


def test_dev_mode_without_keys_is_open(client):
    assert client.post("/api/v1/analyze", json=payload()).status_code == 200


def test_keys_required_once_configured(client, auth_env):
    auth_env()
    assert client.post("/api/v1/analyze", json=payload()).status_code == 401
    assert client.post("/api/v1/analyze", json=payload(), headers={"X-API-Key": "wrong"}).status_code == 401
    assert client.post("/api/v1/analyze", json=payload(), headers=ANALYST).status_code == 200


def test_any_nonempty_key_is_no_longer_accepted(client, auth_env):
    """Regression: production used to accept any non-empty X-API-Key."""
    auth_env()
    for k in ("x", "demo-key", "adminkey ", "ADMINKEY"):
        assert client.get("/api/v1/cases", headers={"X-API-Key": k}).status_code == 401


def test_rbac_matrix(client, auth_env):
    auth_env()
    assert client.get("/api/v1/cases", headers=VIEWER).status_code == 200
    assert client.post("/api/v1/cases", json={"title": "t"}, headers=VIEWER).status_code == 403
    assert client.post("/api/v1/analyze", json=payload(), headers=VIEWER).status_code == 403
    assert client.post("/api/v1/cases", json={"title": "t"}, headers=ANALYST).status_code == 200
    assert client.get("/api/v1/audit/entries", headers=ANALYST).status_code == 403
    assert client.get("/api/v1/audit/entries", headers=ADMIN).status_code == 200
    assert client.get("/api/v1/audit/verify", headers=VIEWER).status_code == 200


def test_production_fails_closed_without_keys(client, monkeypatch):
    monkeypatch.setattr(settings, "environment", "production")
    r = client.post("/api/v1/analyze", json=payload())
    assert r.status_code == 401 and "not configured" in r.json()["message"]
    assert client.get("/health").status_code == 200


def test_public_demo_mode_is_analysis_only_and_non_persisting(client, monkeypatch):
    monkeypatch.setattr(settings, "environment", "production")
    monkeypatch.setattr(settings.api, "public_demo", True)
    r = client.post("/api/v1/analyze", json=payload(tx={"parties": ["Sanctioned Russian Bank"]}))
    d = r.json()
    assert r.status_code == 200 and d["analysis_id"] is None and d["case"] is None and d["audit"] is None
    assert client.get("/api/v1/cases").status_code == 403
    assert client.post("/api/v1/cases", json={"title": "x"}).status_code == 403
    assert client.get("/api/v1/audit/entries").status_code == 403


def test_keystore_parsing_ignores_malformed_entries():
    ks = security.KeyStore("ok:admin:k1, broken, bad:role:k2, :admin:, two:viewer:k3")
    assert len(ks) == 2 and ks.lookup("k1").role == "admin" and ks.lookup("k2") is None and ks.lookup("k3").name == "two"
    assert ks.lookup("") is None and ks.lookup(None) is None


def test_rate_limit_blocks_and_fake_keys_do_not_bypass(client, monkeypatch):
    monkeypatch.setattr(settings.api, "rate_limit_requests", 5)
    codes = [client.get("/api/v1/reference/regimes", headers={"X-API-Key": f"fake-{i}"}).status_code for i in range(9)]
    assert codes[:5] == [200] * 5 and set(codes[5:]) == {429}            # rotating the header changes nothing
    blocked = client.get("/api/v1/reference/regimes")
    assert blocked.status_code == 429 and "Retry-After" in blocked.headers


def test_valid_keys_get_their_own_bucket_and_health_is_exempt(client, auth_env, monkeypatch):
    auth_env()
    monkeypatch.setattr(settings.api, "rate_limit_requests", 3)
    for _ in range(3):
        assert client.get("/api/v1/cases", headers=VIEWER).status_code == 200
    assert client.get("/api/v1/cases", headers=VIEWER).status_code == 429
    assert client.get("/api/v1/cases", headers=ANALYST).status_code == 200      # different principal
    assert all(client.get("/health").status_code == 200 for _ in range(10))


def test_trust_proxy_uses_forwarded_for(client, monkeypatch):
    monkeypatch.setattr(settings.api, "rate_limit_requests", 2)
    monkeypatch.setattr(settings.api, "trust_proxy", True)
    for ip in ("1.1.1.1", "2.2.2.2"):
        assert client.get("/api/v1/reference/regimes", headers={"X-Forwarded-For": ip}).status_code == 200
    for _ in range(2):
        client.get("/api/v1/reference/regimes", headers={"X-Forwarded-For": "1.1.1.1"})
    assert client.get("/api/v1/reference/regimes", headers={"X-Forwarded-For": "1.1.1.1"}).status_code == 429
    assert client.get("/api/v1/reference/regimes", headers={"X-Forwarded-For": "3.3.3.3"}).status_code == 200


def test_cors_wildcard_never_combined_with_credentials(client):
    r = client.get("/health", headers={"Origin": "https://evil.example"})
    assert r.headers.get("access-control-allow-origin") in ("*", None)
    assert r.headers.get("access-control-allow-credentials") != "true"
