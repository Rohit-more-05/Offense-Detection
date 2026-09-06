from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Float, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.logger import get_logger

logger = get_logger(__name__)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Prediction(Base):
    """
    SQLAlchemy ORM model for the `predictions` table.

    Schema is intentionally designed for Phase 2 compatibility:
    - heatmap_path, human_verdict, reviewer_notes, reviewed_at are nullable
    - label / moderation_decision use string literals matching Pydantic Literal types
    """

    __tablename__ = "predictions"

    # ── Primary key ────────────────────────────────────────────────────────────
    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        index=True,
    )

    # ── Upload metadata ────────────────────────────────────────────────────────
    filename: Mapped[str] = mapped_column(String(512), nullable=False)
    image_path: Mapped[str] = mapped_column(String(1024), nullable=False)

    # ── Inference results ──────────────────────────────────────────────────────
    label: Mapped[str] = mapped_column(String(16), nullable=False)        # "Harmful" | "Safe"
    confidence: Mapped[float] = mapped_column(Float, nullable=False)      # 0.0 – 1.0
    moderation_decision: Mapped[str] = mapped_column(String(32), nullable=False)
    # "AUTO_APPROVE" | "AUTO_FLAG" | "HUMAN_REVIEW"

    heatmap_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    execution_time_ms: Mapped[int] = mapped_column(Integer, nullable=False)

    # ── Audit / review fields ──────────────────────────────────────────────────
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    reviewed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    human_verdict: Mapped[str | None] = mapped_column(String(32), nullable=True)
    # "Harmful" | "Non-Harmful"
    reviewer_notes: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    def __repr__(self) -> str:
        return (
            f"<Prediction id={self.id!r} label={self.label!r} "
            f"confidence={self.confidence:.2f} decision={self.moderation_decision!r}>"
        )
