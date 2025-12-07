"""
SentinelAI Configuration Management
===================================

Centralized configuration using Pydantic Settings for type-safe,
environment-aware configuration management.
"""

from typing import List, Optional, Literal
from pydantic_settings import BaseSettings
from pydantic import Field, SecretStr
from functools import lru_cache
import os


class LLMSettings(BaseSettings):
    """LLM Provider Configuration"""
    
    provider: Literal["groq", "huggingface"] = Field(
        default="groq",
        description="LLM provider to use"
    )
    groq_api_key: Optional[SecretStr] = Field(
        default=None,
        env="GROQ_API_KEY"
    )
    groq_model: str = Field(
        default="llama-3.3-70b-versatile",
        description="Groq model to use"
    )
    huggingface_api_key: Optional[SecretStr] = Field(
        default=None,
        env="HUGGINGFACE_API_KEY"
    )
    huggingface_model: str = Field(
        default="meta-llama/Llama-3.1-70B-Instruct",
        description="HuggingFace model to use"
    )
    temperature: float = Field(default=0.0, ge=0, le=2)
    max_tokens: int = Field(default=4096, ge=1)
    max_retries: int = Field(default=3, ge=1)
    timeout: int = Field(default=60, ge=1)

    class Config:
        env_prefix = "SENTINEL_LLM_"


class DatabaseSettings(BaseSettings):
    """Database Configuration"""
    
    # PostgreSQL Settings
    postgres_host: str = Field(default="localhost")
    postgres_port: int = Field(default=5432)
    postgres_user: str = Field(default="sentinel")
    postgres_password: SecretStr = Field(default=SecretStr("sentinel_password"))
    postgres_db: str = Field(default="sentinelai")
    
    # Direct URL override (for Render.com and other PaaS)
    database_url_override: Optional[str] = Field(default=None, alias="DATABASE_URL")
    redis_url_override: Optional[str] = Field(default=None, alias="REDIS_URL")
    
    # Redis Settings (for caching & pub/sub)
    redis_host: str = Field(default="localhost")
    redis_port: int = Field(default=6379)
    redis_password: Optional[SecretStr] = Field(default=None)
    redis_db: int = Field(default=0)
    
    # Neo4j Settings (for graph relationships)
    neo4j_uri: str = Field(default="bolt://localhost:7687")
    neo4j_user: str = Field(default="neo4j")
    neo4j_password: SecretStr = Field(default=SecretStr("neo4j_password"))

    @property
    def postgres_url(self) -> str:
        """Get PostgreSQL URL, preferring DATABASE_URL if set"""
        if self.database_url_override:
            url = self.database_url_override
            # Convert postgres:// to postgresql+asyncpg:// for SQLAlchemy async
            if url.startswith("postgres://"):
                url = url.replace("postgres://", "postgresql+asyncpg://", 1)
            elif url.startswith("postgresql://"):
                url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
            return url
        password = self.postgres_password.get_secret_value()
        return f"postgresql+asyncpg://{self.postgres_user}:{password}@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
    
    @property
    def postgres_url_sync(self) -> str:
        """Get sync PostgreSQL URL for migrations"""
        if self.database_url_override:
            url = self.database_url_override
            # Convert to sync driver
            if url.startswith("postgres://"):
                return url.replace("postgres://", "postgresql://", 1)
            if "+asyncpg" in url:
                return url.replace("+asyncpg", "")
            return url
        password = self.postgres_password.get_secret_value()
        return f"postgresql://{self.postgres_user}:{password}@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"

    @property
    def redis_url(self) -> str:
        """Get Redis URL, preferring REDIS_URL if set"""
        if self.redis_url_override:
            return self.redis_url_override
        if self.redis_password:
            return f"redis://:{self.redis_password.get_secret_value()}@{self.redis_host}:{self.redis_port}/{self.redis_db}"
        return f"redis://{self.redis_host}:{self.redis_port}/{self.redis_db}"

    class Config:
        env_prefix = "SENTINEL_DB_"
        populate_by_name = True


class RiskSettings(BaseSettings):
    """Risk Assessment Configuration"""
    
    # Risk Thresholds
    low_risk_threshold: int = Field(default=30)
    medium_risk_threshold: int = Field(default=60)
    high_risk_threshold: int = Field(default=80)
    critical_risk_threshold: int = Field(default=95)
    
    # Transaction Thresholds
    large_transaction_threshold: float = Field(default=10000.0)
    very_large_transaction_threshold: float = Field(default=100000.0)
    structuring_threshold: float = Field(default=9500.0)
    
    # Velocity Thresholds
    max_daily_transactions: int = Field(default=10)
    max_daily_amount: float = Field(default=50000.0)
    new_account_days: int = Field(default=30)
    
    # High-Risk Jurisdictions
    high_risk_countries: List[str] = Field(
        default=["IR", "KP", "SY", "CU", "MM", "RU", "BY", "VE", "ZW", "AF", "YE", "SO", "LY"]
    )
    tax_havens: List[str] = Field(
        default=["KY", "VG", "BM", "PA", "MT", "AE", "JE", "GG", "IM", "BZ", "SC", "MU", "LI", "MC"]
    )
    grey_list_countries: List[str] = Field(
        default=["PK", "NG", "PH", "TZ", "UG", "JM", "HT", "AL", "BA"]
    )

    class Config:
        env_prefix = "SENTINEL_RISK_"


class APISettings(BaseSettings):
    """API Server Configuration"""
    
    host: str = Field(default="0.0.0.0")
    port: int = Field(default=8000)
    workers: int = Field(default=4)
    reload: bool = Field(default=False)
    debug: bool = Field(default=False)
    
    # CORS
    cors_origins: List[str] = Field(default=["*"])
    cors_allow_credentials: bool = Field(default=True)
    
    # Rate Limiting
    rate_limit_requests: int = Field(default=100)
    rate_limit_period: int = Field(default=60)  # seconds
    
    # Authentication
    jwt_secret: SecretStr = Field(default=SecretStr("your-super-secret-jwt-key-change-in-production"))
    jwt_algorithm: str = Field(default="HS256")
    jwt_expiry_hours: int = Field(default=24)
    
    # API Keys
    api_key_header: str = Field(default="X-API-Key")

    class Config:
        env_prefix = "SENTINEL_API_"


class MonitoringSettings(BaseSettings):
    """Monitoring & Observability Configuration"""
    
    # Logging
    log_level: str = Field(default="INFO")
    log_format: str = Field(default="json")  # json or text
    log_file: Optional[str] = Field(default="logs/sentinelai.log")
    
    # Metrics
    metrics_enabled: bool = Field(default=True)
    metrics_port: int = Field(default=9090)
    
    # Tracing
    tracing_enabled: bool = Field(default=False)
    jaeger_host: str = Field(default="localhost")
    jaeger_port: int = Field(default=6831)
    
    # Health Checks
    health_check_interval: int = Field(default=30)

    class Config:
        env_prefix = "SENTINEL_MONITOR_"


class Settings(BaseSettings):
    """Master Settings Configuration"""
    
    # Application Info
    app_name: str = Field(default="SentinelAI")
    app_version: str = Field(default="1.0.0")
    environment: Literal["development", "staging", "production"] = Field(
        default="development"
    )
    
    # Nested Settings
    llm: LLMSettings = Field(default_factory=LLMSettings)
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    risk: RiskSettings = Field(default_factory=RiskSettings)
    api: APISettings = Field(default_factory=APISettings)
    monitoring: MonitoringSettings = Field(default_factory=MonitoringSettings)

    class Config:
        env_prefix = "SENTINEL_"
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance"""
    return Settings()


# Global settings instance
settings = get_settings()
