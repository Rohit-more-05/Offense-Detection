from __future__ import annotations

import re
import textwrap

from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings
from app.logger import get_logger

logger = get_logger(__name__)

settings = get_settings()


def _mask_password(url: str) -> str:
    """Replace password in DSN with *** for safe logging."""
    return re.sub(r"(:)([^:@]+)(@)", r"\1***\3", url)


# ── Engine ─────────────────────────────────────────────────────────────────────
# psycopg3 requires the dialect prefix `postgresql+psycopg://`
_raw_url = settings.database_url
if _raw_url.startswith("postgresql://") and "+psycopg" not in _raw_url:
    _raw_url = _raw_url.replace("postgresql://", "postgresql+psycopg://", 1)

masked_url = _mask_password(_raw_url)
logger.info(
    "[database] Creating SQLAlchemy engine → host: %s",
    masked_url,
)

try:
    engine = create_engine(
        _raw_url,
        pool_pre_ping=True,       # validates connections before use
        pool_size=5,
        max_overflow=10,
        # psycopg3 connect_args: use connect_timeout (seconds)
        connect_args={"connect_timeout": 10},
    )
    logger.info("[database] Supabase connection pool initialized → %s", masked_url)
except Exception as exc:
    logger.error("[database] Engine creation FAILED — reason: %s", str(exc), exc_info=True)
    raise


# ── Session factory ────────────────────────────────────────────────────────────
SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
    class_=Session,
)


# ── Declarative base ───────────────────────────────────────────────────────────
class Base(DeclarativeBase):
    pass


# ── Dependency ─────────────────────────────────────────────────────────────────
def get_db():
    """FastAPI dependency: yields a DB session and guarantees close on exit."""
    logger.debug("[get_db] Opening DB session")
    db = SessionLocal()
    try:
        yield db
    except Exception as exc:
        logger.error("[get_db] Session error — rolling back: %s", str(exc), exc_info=True)
        db.rollback()
        raise
    finally:
        logger.debug("[get_db] Closing DB session")
        db.close()


# ── Health checks ──────────────────────────────────────────────────────────────
def verify_connection() -> None:
    """Run SELECT 1 to confirm live Supabase connectivity. Called at startup."""
    logger.info("[verify_connection] START — testing Supabase connectivity")
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        logger.info("[verify_connection] SUCCESS — Supabase connection successful")
    except Exception as exc:
        logger.error(
            "[verify_connection] FAILED — Supabase connection FAILED: %s", str(exc), exc_info=True
        )
        raise


def verify_predictions_table() -> None:
    """Query information_schema to confirm predictions table exists."""
    logger.info("[verify_predictions_table] START — checking predictions table existence")
    try:
        with engine.connect() as conn:
            result = conn.execute(
                text(
                    textwrap.dedent("""
                        SELECT table_name
                        FROM information_schema.tables
                        WHERE table_schema = 'public'
                          AND table_name   = 'predictions'
                    """)
                )
            )
            row = result.fetchone()
        if row:
            logger.info("[verify_predictions_table] SUCCESS — predictions table exists as required")
        else:
            logger.warning(
                "[verify_predictions_table] predictions table NOT FOUND — "
                "run 'alembic upgrade head' to create it"
            )
    except Exception as exc:
        logger.error(
            "[verify_predictions_table] FAILED — reason: %s", str(exc), exc_info=True
        )
        raise


def init_db() -> None:
    """
    Create all tables from ORM metadata if they don't exist yet.
    This is a fallback for environments without Alembic; prefer `alembic upgrade head`.
    """
    logger.info("[init_db] START — running Base.metadata.create_all()")
    try:
        # Import models so their metadata is registered on Base before create_all
        from app.models import prediction  # noqa: F401

        Base.metadata.create_all(bind=engine)
        logger.info("[init_db] SUCCESS — all tables created/verified")
    except Exception as exc:
        logger.error("[init_db] FAILED — reason: %s", str(exc), exc_info=True)
        raise
