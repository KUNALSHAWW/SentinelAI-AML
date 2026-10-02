"""Settings: .env must work, unknown keys must be ignored (regression: startup crash)."""

from sentinelai.core.config import APISettings, DatabaseSettings, LLMSettings, RiskSettings, Settings


def test_env_example_style_dotenv_does_not_crash(tmp_path, monkeypatch):
    (tmp_path / ".env").write_text(
        "SENTINEL_ENVIRONMENT=production\nGROQ_API_KEY=gsk_test\nSENTINEL_LLM_PROVIDER=groq\n"
        "SENTINEL_DB_POSTGRES_HOST=db\nSENTINEL_API_CORS_ORIGINS=https://a.example,https://b.example\n"
        "SOMETHING_UNRELATED=1\nSENTINEL_NOT_A_FIELD=x\n")
    monkeypatch.chdir(tmp_path)
    for key in ("SENTINEL_ENVIRONMENT", "SENTINEL_DB_POSTGRES_HOST"):
        monkeypatch.delenv(key, raising=False)   # real env vars outrank .env
    s = Settings()
    assert s.environment == "production"
    assert s.llm.api_key_configured                      # nested settings read .env too
    assert s.api.cors_origins == ["https://a.example", "https://b.example"]
    assert s.database.url == "postgresql+asyncpg://sentinel:sentinel_password@db:5432/sentinelai"


def test_cors_accepts_json_and_csv(monkeypatch):
    monkeypatch.setenv("SENTINEL_API_CORS_ORIGINS", '["https://x.example"]')
    assert APISettings().cors_origins == ["https://x.example"]
    monkeypatch.setenv("SENTINEL_API_CORS_ORIGINS", "https://x.example , https://y.example")
    assert APISettings().cors_origins == ["https://x.example", "https://y.example"]


def test_port_env_alias(monkeypatch):
    monkeypatch.setenv("PORT", "10000")
    assert APISettings().port == 10000
    monkeypatch.setenv("SENTINEL_API_PORT", "9001")
    assert APISettings().port == 9001


def test_database_url_selection(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgres://u:p@h:5432/d")
    d = DatabaseSettings()
    assert d.url == "postgresql+asyncpg://u:p@h:5432/d" and not d.is_sqlite
    assert d.sync_url == "postgresql://u:p@h:5432/d"
    monkeypatch.delenv("DATABASE_URL")
    assert DatabaseSettings().is_sqlite


def test_redis_is_optional(monkeypatch):
    monkeypatch.delenv("REDIS_URL", raising=False)
    assert DatabaseSettings().redis_url is None
    monkeypatch.setenv("REDIS_URL", "redis://r:6379/1")
    assert DatabaseSettings().redis_url == "redis://r:6379/1"


def test_fx_override_and_thresholds(monkeypatch):
    monkeypatch.setenv("SENTINEL_RISK_FX_RATES", '{"INR": 0.02}')
    r = RiskSettings()
    assert r.fx_rates == {"INR": 0.02}
    assert r.medium_risk_threshold < r.high_risk_threshold < r.critical_risk_threshold


def test_web_search_and_pii_defaults_are_privacy_preserving():
    llm = LLMSettings()
    assert llm.web_search_enabled is False and llm.redact_pii is True and llm.max_uplift <= 20


def test_postgres_tls_defaults_and_sslmode_translation(monkeypatch):
    """Regression: Render PostgreSQL requires TLS; asyncpg needs ssl=..., and rejects libpq's ?sslmode=."""
    monkeypatch.setenv("DATABASE_URL", "postgres://u:p@dpg-abc-a/db")
    d = DatabaseSettings()
    assert d.connect_args == {"ssl": "prefer"} and d.url == "postgresql+asyncpg://u:p@dpg-abc-a/db"
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@h.render.com/db?sslmode=require")
    d = DatabaseSettings()
    assert d.connect_args == {"ssl": "require"} and "sslmode" not in d.url
    monkeypatch.setenv("SENTINEL_DB_SSL_MODE", "disable")
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@h/db")
    assert DatabaseSettings().connect_args == {"ssl": "disable"}
    monkeypatch.delenv("DATABASE_URL")
    assert DatabaseSettings().connect_args == {}              # SQLite needs none
