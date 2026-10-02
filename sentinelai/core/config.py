"""
SentinelAI Configuration
========================

Type-safe settings. Every settings group reads both real environment
variables *and* a local ``.env`` file, and unknown keys are ignored, so the
``.env.example`` shipped with the repo works as-is.
"""

from __future__ import annotations

import json
from functools import lru_cache
from typing import Annotated, Dict, List, Literal, Optional

from pydantic import AliasChoices, Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


def _config(prefix: str) -> SettingsConfigDict:
    return SettingsConfigDict(
        env_prefix=prefix,
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )


def _csv_or_json_list(value):
    """Accept ``["a","b"]`` (JSON) or ``a,b`` (CSV) for list-typed env vars."""
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return []
        if text.startswith("["):
            return json.loads(text)
        return [item.strip() for item in text.split(",") if item.strip()]
    return value


class LLMSettings(BaseSettings):
    """LLM provider and agent behaviour."""

    model_config = _config("SENTINEL_LLM_")

    provider: Literal["groq", "huggingface"] = "groq"
    groq_api_key: Optional[SecretStr] = Field(
        default=None, validation_alias=AliasChoices("GROQ_API_KEY", "SENTINEL_LLM_GROQ_API_KEY")
    )
    groq_model: str = "qwen/qwen3.6-27b"
    tavily_api_key: Optional[SecretStr] = Field(
        default=None, validation_alias=AliasChoices("TAVILY_API_KEY", "SENTINEL_LLM_TAVILY_API_KEY")
    )
    huggingface_api_key: Optional[SecretStr] = Field(
        default=None,
        validation_alias=AliasChoices("HUGGINGFACE_API_KEY", "SENTINEL_LLM_HUGGINGFACE_API_KEY"),
    )
    huggingface_model: str = "meta-llama/Llama-3.1-70B-Instruct"
    temperature: float = Field(default=0.0, ge=0, le=2)
    max_tokens: int = Field(default=4096, ge=1)
    max_retries: int = Field(default=3, ge=1)
    timeout: int = Field(default=60, ge=1)

    # --- agent safety / privacy -------------------------------------------
    web_search_enabled: bool = Field(
        default=False,
        description="Allow research agents to query Tavily/DuckDuckGo. Off by default: "
        "customer data must not leave the perimeter unless explicitly enabled.",
    )
    redact_pii: bool = Field(default=True, description="Redact IDs/emails/phones before any LLM call.")
    agent_timeout_s: int = Field(default=90, ge=5, description="Per-agent wall-clock budget.")
    agent_recursion_limit: int = Field(default=25, ge=3)
    max_uplift: int = Field(
        default=15, ge=0, le=50,
        description="Maximum risk points the LLM layer may ADD. It can never lower a deterministic score.",
    )

    @property
    def api_key_configured(self) -> bool:
        if self.provider == "groq":
            return bool(self.groq_api_key and self.groq_api_key.get_secret_value())
        return bool(self.huggingface_api_key and self.huggingface_api_key.get_secret_value())


class DatabaseSettings(BaseSettings):
    """Persistence. SQLite by default (zero-config); PostgreSQL in production."""

    model_config = _config("SENTINEL_DB_")

    database_url_override: Optional[str] = Field(default=None, validation_alias="DATABASE_URL")
    sqlite_path: str = "data/sentinelai.db"
    auto_create_tables: bool = Field(
        default=True, description="create_all() on startup (dev convenience). Disable when using Alembic migrations.")

    postgres_host: Optional[str] = None
    postgres_port: int = 5432
    postgres_user: str = "sentinel"
    postgres_password: SecretStr = SecretStr("sentinel_password")
    postgres_db: str = "sentinelai"

    redis_url_override: Optional[str] = Field(default=None, validation_alias="REDIS_URL")
    redis_host: Optional[str] = None
    redis_port: int = 6379
    redis_password: Optional[SecretStr] = None
    redis_db: int = 0

    ssl_mode: Literal["prefer", "require", "disable", "verify-full"] = Field(
        default="prefer",
        description="PostgreSQL TLS. 'prefer' tries SSL and falls back to plain (works on Render, which requires TLS, "
                    "and on local/compose databases). A sslmode= in DATABASE_URL overrides this.")

    @staticmethod
    def _split_sslmode(url: str):
        """asyncpg rejects libpq's ?sslmode=; strip it and return (clean_url, mode_or_None)."""
        from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
        parts = urlsplit(url)
        query = parse_qsl(parts.query, keep_blank_values=True)
        mode = next((v for k, v in query if k in ("sslmode", "ssl")), None)
        rest = [(k, v) for k, v in query if k not in ("sslmode", "ssl")]
        return urlunsplit(parts._replace(query=urlencode(rest))), mode

    @property
    def connect_args(self) -> dict:
        """Driver arguments for the async engine (TLS for PostgreSQL)."""
        if not self.url.startswith("postgresql"):
            return {}
        mode = self.ssl_mode
        if self.database_url_override:
            _, from_url = self._split_sslmode(self.database_url_override)
            mode = from_url or mode
        mode = {"allow": "prefer", "verify-ca": "verify-full", "true": "require"}.get(mode, mode)
        return {"ssl": mode}

    @staticmethod
    def _async_url(url: str) -> str:
        if url.startswith("postgres://"):
            return url.replace("postgres://", "postgresql+asyncpg://", 1)
        if url.startswith("postgresql://"):
            return url.replace("postgresql://", "postgresql+asyncpg://", 1)
        if url.startswith("sqlite://") and "+aiosqlite" not in url:
            return url.replace("sqlite://", "sqlite+aiosqlite://", 1)
        return url

    @property
    def url(self) -> str:
        """Async SQLAlchemy URL."""
        if self.database_url_override:
            url = self._async_url(self.database_url_override)
            return self._split_sslmode(url)[0] if url.startswith("postgresql") else url
        if self.postgres_host:
            pw = self.postgres_password.get_secret_value()
            return (
                f"postgresql+asyncpg://{self.postgres_user}:{pw}"
                f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
            )
        return f"sqlite+aiosqlite:///{self.sqlite_path}"

    @property
    def sync_url(self) -> str:
        """Sync URL for Alembic."""
        return (
            self.url.replace("+asyncpg", "").replace("+aiosqlite", "")
        )

    @property
    def postgres_url(self) -> str:  # backwards-compatible alias
        return self.url

    @property
    def is_sqlite(self) -> bool:
        return self.url.startswith("sqlite")

    @property
    def redis_url(self) -> Optional[str]:
        if self.redis_url_override:
            return self.redis_url_override or None
        if self.redis_host:
            if self.redis_password:
                return f"redis://:{self.redis_password.get_secret_value()}@{self.redis_host}:{self.redis_port}/{self.redis_db}"
            return f"redis://{self.redis_host}:{self.redis_port}/{self.redis_db}"
        return None


class RiskSettings(BaseSettings):
    """Scoring thresholds. All amounts are USD-equivalent unless stated."""

    model_config = _config("SENTINEL_RISK_")

    regime: Literal["US_BSA", "IN_PMLA", "EU_AMLD"] = "US_BSA"

    # Score bands: LOW < medium <= MEDIUM < high <= HIGH < critical <= CRITICAL
    medium_risk_threshold: int = Field(default=30, ge=1, le=100)
    high_risk_threshold: int = Field(default=60, ge=1, le=100)
    critical_risk_threshold: int = Field(default=80, ge=1, le=100)
    sar_score_threshold: int = Field(default=60, ge=1, le=100)

    large_transaction_threshold: float = 10_000.0
    very_large_transaction_threshold: float = 100_000.0

    max_daily_transactions: int = 10
    max_daily_amount: float = 50_000.0
    new_account_days: int = 30

    # Fuzzy-matching calibration (OFAC: "calibrate to your risk profile and test routinely")
    sanctions_match_threshold: float = Field(default=0.92, ge=0.5, le=1.0)
    sanctions_review_threshold: float = Field(default=0.85, ge=0.5, le=1.0)
    pep_match_threshold: float = Field(default=0.92, ge=0.5, le=1.0)
    lists_dir: str = "data/lists"

    jurisdictions_file: Optional[str] = None
    sanctions_list_file: Optional[str] = None
    fx_rates: Annotated[Dict[str, float], NoDecode] = Field(
        default_factory=dict, description="Override USD-per-unit FX rates, e.g. '{\"INR\":0.0113}'."
    )

    @field_validator("fx_rates", mode="before")
    @classmethod
    def _parse_fx(cls, value):
        if isinstance(value, str):
            return json.loads(value) if value.strip() else {}
        return value


class APISettings(BaseSettings):
    """HTTP server, auth and abuse protection."""

    model_config = _config("SENTINEL_API_")

    host: str = "0.0.0.0"
    port: int = Field(default=8000, validation_alias=AliasChoices("SENTINEL_API_PORT", "PORT"))
    workers: int = 1
    reload: bool = False
    debug: bool = False

    cors_origins: Annotated[List[str], NoDecode] = ["*"]
    rate_limit_requests: int = 100
    rate_limit_period: int = 60
    demo_rate_limit_requests: int = Field(default=20, description="Stricter limit for unauthenticated public-demo callers.")
    trust_proxy: bool = Field(default=False, description="Honour X-Forwarded-For for client IPs.")

    api_keys: str = Field(
        default="",
        description="Comma-separated 'name:role:key' entries. Roles: viewer, analyst, admin.",
    )
    public_demo: bool = Field(
        default=False,
        description="Allow unauthenticated, rate-limited, NON-persisting analysis for public demos.",
    )
    api_key_header: str = "X-API-Key"

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _parse_origins(cls, value):
        return _csv_or_json_list(value)


class MonitoringSettings(BaseSettings):
    """Logging and metrics."""

    model_config = _config("SENTINEL_MONITOR_")

    log_level: str = "INFO"
    log_format: Literal["json", "text"] = "json"
    log_file: Optional[str] = None
    metrics_enabled: bool = True


class Settings(BaseSettings):
    """Master settings object."""

    model_config = _config("SENTINEL_")

    app_name: str = "SentinelAI"
    app_version: str = "2.0.0"
    environment: Literal["development", "staging", "production", "test"] = "development"

    llm: LLMSettings = Field(default_factory=LLMSettings)
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    risk: RiskSettings = Field(default_factory=RiskSettings)
    api: APISettings = Field(default_factory=APISettings)
    monitoring: MonitoringSettings = Field(default_factory=MonitoringSettings)

    @property
    def is_production(self) -> bool:
        return self.environment == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
