"""Async database engine / session management."""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator, Optional

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from sentinelai.core.config import settings
from sentinelai.core.logging import get_logger
from sentinelai.models.database import Base

logger = get_logger(__name__)

_engine: Optional[AsyncEngine] = None
_sessionmaker: Optional[async_sessionmaker[AsyncSession]] = None


def configure_engine(url: Optional[str] = None) -> AsyncEngine:
    """(Re)create the global engine. ``sqlite+aiosqlite:///:memory:`` is supported for tests."""
    global _engine, _sessionmaker
    url = url or settings.database.url
    kwargs = {}
    if url.startswith("sqlite"):
        if ":memory:" in url:
            kwargs.update(poolclass=StaticPool, connect_args={"check_same_thread": False})
        else:
            path = url.split("///", 1)[-1]
            Path(path).parent.mkdir(parents=True, exist_ok=True)
    else:
        kwargs.update(pool_pre_ping=True)
    _engine = create_async_engine(url, **kwargs)
    if url.startswith("sqlite"):
        from sqlalchemy import event

        @event.listens_for(_engine.sync_engine, "connect")
        def _sqlite_connect(dbapi_conn, _record):
            # Take transaction control away from pysqlite: by default it does not emit BEGIN before
            # SAVEPOINT, so a ROLLBACK silently fails to undo work done inside a savepoint
            # (documented SQLAlchemy "pysqlite serializable isolation / SAVEPOINT" recipe).
            dbapi_conn.isolation_level = None
            if ":memory:" not in url:
                cur = dbapi_conn.cursor()          # WAL + busy timeout: concurrent readers/writers without 'database is locked'
                cur.execute("PRAGMA journal_mode=WAL")
                cur.execute("PRAGMA busy_timeout=10000")
                cur.close()

        @event.listens_for(_engine.sync_engine, "begin")
        def _sqlite_begin(conn):
            # IMMEDIATE takes the (single) write lock up front: no snapshot-upgrade failures between
            # concurrent writers. Transactions are kept short by design (see AnalysisService).
            conn.exec_driver_sql("BEGIN IMMEDIATE" if ":memory:" not in url else "BEGIN")
    _sessionmaker = async_sessionmaker(_engine, expire_on_commit=False)
    return _engine


def get_engine() -> AsyncEngine:
    return _engine or configure_engine()


def get_sessionmaker() -> async_sessionmaker[AsyncSession]:
    if _sessionmaker is None:
        configure_engine()
    return _sessionmaker  # type: ignore[return-value]


@asynccontextmanager
async def session_scope() -> AsyncIterator[AsyncSession]:
    """Transactional scope: commit on success, roll back on error."""
    async with get_sessionmaker()() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def init_db() -> None:
    """Create tables when they do not exist (dev/test convenience; prod uses Alembic)."""
    async with get_engine().begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def dispose_engine() -> None:
    global _engine, _sessionmaker
    if _engine is not None:
        await _engine.dispose()
    _engine = _sessionmaker = None


async def ping() -> bool:
    from sqlalchemy import text
    try:
        async with get_engine().connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except Exception as exc:
        logger.warning("Database ping failed: %s", exc)
        return False
