"""
Alembic migration environment.

Reads DATABASE_URL from the .env file so migrations can be run with:
    alembic upgrade head
    alembic revision --autogenerate -m "description"
    alembic downgrade -1
"""

from __future__ import annotations

import os
import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from dotenv import load_dotenv
from sqlalchemy import engine_from_config, pool

# ── Add backend/ to sys.path so `app.*` imports resolve ───────────────────────
BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

# ── Load .env before importing app modules ─────────────────────────────────────
load_dotenv(BACKEND_DIR / ".env")

# ── Import your models so Alembic sees the full metadata ──────────────────────
from app.database import Base  # noqa: E402
from app.models import prediction  # noqa: F401, E402  — registers model on Base

# ── Alembic Config object ──────────────────────────────────────────────────────
config = context.config

# Override sqlalchemy.url from environment (takes priority over alembic.ini)
database_url = os.environ.get("DATABASE_URL")
if database_url:
    # psycopg3 dialect: rewrite postgresql:// → postgresql+psycopg://
    if database_url.startswith("postgresql://") and "+psycopg" not in database_url:
        database_url = database_url.replace("postgresql://", "postgresql+psycopg://", 1)
    config.set_main_option("sqlalchemy.url", database_url)

# Apply Python logging config from alembic.ini
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Target metadata for autogenerate support
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """
    Run migrations in 'offline' mode.
    Generates SQL without a live DB connection — useful for review/CI.
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """
    Run migrations in 'online' mode with a live Supabase connection.
    Uses NullPool so connections are not shared across processes.
    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            compare_server_default=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
