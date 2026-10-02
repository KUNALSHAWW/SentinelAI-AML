"""Shared fixtures. Environment is pinned *before* sentinelai is imported."""

import os
import tempfile
from datetime import datetime, timedelta, timezone

for key in ("GROQ_API_KEY", "SENTINEL_LLM_GROQ_API_KEY", "TAVILY_API_KEY", "DATABASE_URL", "REDIS_URL"):
    os.environ.pop(key, None)
os.environ.update({
    "SENTINEL_ENVIRONMENT": "development",
    "SENTINEL_MONITOR_LOG_LEVEL": "WARNING",
    "SENTINEL_DB_SQLITE_PATH": os.path.join(tempfile.mkdtemp(prefix="sentinel-test-"), "t.db"),
    "SENTINEL_API_RATE_LIMIT_REQUESTS": "100000",
})

import pytest  # noqa: E402

from sentinelai.core import cache as cache_module  # noqa: E402
from sentinelai.core.config import settings  # noqa: E402
from sentinelai.core import security  # noqa: E402
from sentinelai.engine import DetectionEngine, build_input  # noqa: E402

NOW = datetime(2026, 10, 1, 12, 0, tzinfo=timezone.utc)


def ts(hours_ago: float) -> str:
    return (NOW - timedelta(hours=hours_ago)).isoformat()


@pytest.fixture
def engine() -> DetectionEngine:
    return DetectionEngine()


@pytest.fixture
def make_ctx():
    def _make(tx=None, customer=None, network=None, regime="US_BSA", **kw):
        transaction = {"amount": 5000, "currency": "USD", "transaction_type": "WIRE_TRANSFER", "origin_country": "US",
                       "destination_country": "CA", "parties": ["Acme Supplies"], "documents": ["Invoice"], "timestamp": NOW.isoformat()}
        transaction.update(tx or {})
        cust = {"name": "Jane Roe", "customer_id": "c1", "customer_type": "INDIVIDUAL", "account_age_days": 800}
        cust.update(customer or {})
        return build_input(transaction, cust, network, regime=regime, **kw)
    return _make


@pytest.fixture
def run(engine, make_ctx):
    def _run(**kw):
        return engine.run(make_ctx(**kw))
    return _run


@pytest.fixture
async def db(tmp_path):
    """Fresh on-disk SQLite per test (in-memory + StaticPool cannot model concurrent sessions)."""
    from sentinelai.db import session as dbs
    dbs.configure_engine(f"sqlite+aiosqlite:///{tmp_path / 'test.db'}")
    await dbs.init_db()
    yield dbs
    await dbs.dispose_engine()


@pytest.fixture
def client(tmp_path):
    from fastapi.testclient import TestClient
    from sentinelai.api import deps
    from sentinelai.api.app import create_app
    from sentinelai.db import session as dbs
    dbs.configure_engine(f"sqlite+aiosqlite:///{tmp_path / 'test.db'}")
    deps.reset_services()
    cache_module.reset_cache()
    with TestClient(create_app()) as c:
        yield c


@pytest.fixture
def client_soft(tmp_path):
    """Like `client`, but server errors become HTTP 500 responses instead of re-raising (tests error handlers)."""
    from fastapi.testclient import TestClient
    from sentinelai.api import deps
    from sentinelai.api.app import create_app
    from sentinelai.db import session as dbs
    dbs.configure_engine(f"sqlite+aiosqlite:///{tmp_path / 'test.db'}")
    deps.reset_services()
    with TestClient(create_app(), raise_server_exceptions=False) as c:
        yield c


@pytest.fixture
def auth_env(monkeypatch):
    """Switch the app into API-key mode (production-like auth)."""
    def _apply(keys="alice:admin:adminkey,bob:analyst:analystkey,eve:viewer:viewerkey", **extra):
        monkeypatch.setattr(settings.api, "api_keys", keys)
        for k, v in extra.items():
            monkeypatch.setattr(settings.api if hasattr(settings.api, k) else settings, k, v)
        security.get_keystore(reload=True)
    yield _apply
    monkeypatch.undo()
    security.get_keystore(reload=True)


@pytest.fixture(autouse=True)
def _isolate_cache_and_services():
    """Global caches must never leak between tests (a cached agent result once hid a failure path)."""
    cache_module.reset_cache()
    yield
    cache_module.reset_cache()
