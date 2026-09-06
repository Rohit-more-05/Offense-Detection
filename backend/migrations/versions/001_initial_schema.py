"""001_initial_schema — Create predictions table

Revision ID: 001
Revises: (base)
Create Date: 2026-09-06

This migration creates the initial `predictions` table matching the SRS
schema specification. All columns are locked to Phase 1 contract; future
phases add columns via new migrations using `alembic revision --autogenerate`.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# ── Revision identifiers ────────────────────────────────────────────────────
revision: str = "001"
down_revision: str | None = None  # base migration
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    """Create the predictions table."""
    op.create_table(
        "predictions",
        # ── Primary key ────────────────────────────────────────────────────
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=False),
            primary_key=True,
            nullable=False,
            comment="UUID primary key",
        ),
        # ── Upload metadata ────────────────────────────────────────────────
        sa.Column("filename", sa.String(512), nullable=False, comment="Original filename"),
        sa.Column("image_path", sa.String(1024), nullable=False, comment="Server-side saved path"),
        # ── Inference results ──────────────────────────────────────────────
        sa.Column(
            "label",
            sa.String(16),
            nullable=False,
            comment="Harmful | Safe",
        ),
        sa.Column(
            "confidence",
            sa.Float(),
            nullable=False,
            comment="Model confidence 0.0 – 1.0",
        ),
        sa.Column(
            "moderation_decision",
            sa.String(32),
            nullable=False,
            comment="AUTO_APPROVE | AUTO_FLAG | HUMAN_REVIEW",
        ),
        sa.Column(
            "heatmap_path",
            sa.String(1024),
            nullable=True,
            comment="Path to attention heatmap (Phase 2)",
        ),
        sa.Column(
            "execution_time_ms",
            sa.Integer(),
            nullable=False,
            comment="End-to-end inference time in ms",
        ),
        # ── Audit fields ───────────────────────────────────────────────────
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
            comment="UTC timestamp of submission",
        ),
        sa.Column(
            "reviewed",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("FALSE"),
            comment="True once a human or auto decision is final",
        ),
        sa.Column(
            "human_verdict",
            sa.String(32),
            nullable=True,
            comment="Harmful | Non-Harmful (set by moderator)",
        ),
        sa.Column(
            "reviewer_notes",
            sa.String(2048),
            nullable=True,
            comment="Optional moderator notes",
        ),
        sa.Column(
            "reviewed_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="UTC timestamp of human review",
        ),
    )

    # ── Indexes ────────────────────────────────────────────────────────────────
    op.create_index(
        "ix_predictions_id",
        "predictions",
        ["id"],
        unique=True,
    )
    op.create_index(
        "ix_predictions_moderation_decision",
        "predictions",
        ["moderation_decision"],
    )
    op.create_index(
        "ix_predictions_reviewed",
        "predictions",
        ["reviewed"],
    )
    op.create_index(
        "ix_predictions_created_at",
        "predictions",
        ["created_at"],
    )


def downgrade() -> None:
    """Drop the predictions table and its indexes."""
    op.drop_index("ix_predictions_created_at", table_name="predictions")
    op.drop_index("ix_predictions_reviewed", table_name="predictions")
    op.drop_index("ix_predictions_moderation_decision", table_name="predictions")
    op.drop_index("ix_predictions_id", table_name="predictions")
    op.drop_table("predictions")
