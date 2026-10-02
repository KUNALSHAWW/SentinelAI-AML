"""Alembic environment - uses the application's async URL, so no extra sync driver is required."""

import asyncio
import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sentinelai.core.config import settings  # noqa: E402
from sentinelai.models.database import Base  # noqa: E402

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name, disable_existing_loggers=False)

# An explicitly provided URL (tests, CI) wins over the application settings.
if not config.get_main_option("sqlalchemy.url") or config.get_main_option("sqlalchemy.url").startswith("driver://"):
    config.set_main_option("sqlalchemy.url", settings.database.url)

target_metadata = Base.metadata
IS_SQLITE = config.get_main_option("sqlalchemy.url").startswith("sqlite")


def run_migrations_offline() -> None:
    context.configure(url=config.get_main_option("sqlalchemy.url"), target_metadata=target_metadata,
                      literal_binds=True, dialect_opts={"paramstyle": "named"}, compare_type=True,
                      render_as_batch=IS_SQLITE)
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata, compare_type=True,
                      render_as_batch=IS_SQLITE)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    connectable = async_engine_from_config(config.get_section(config.config_ini_section, {}), prefix="sqlalchemy.",
                                           poolclass=pool.NullPool, connect_args=settings.database.connect_args)
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_async_migrations())
