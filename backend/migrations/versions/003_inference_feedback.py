"""Record inference provenance and human feedback training inputs.

Revision ID: 003
Revises: 002
"""
from alembic import op
import sqlalchemy as sa

revision = "003"
down_revision = "002"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("predictions") as batch:
        batch.alter_column("confidence", existing_type=sa.Float(), nullable=True)
        batch.add_column(sa.Column("extracted_text", sa.Text(), nullable=True))
        batch.add_column(sa.Column("image_sha256", sa.String(64), nullable=True))
        batch.add_column(sa.Column("model_version", sa.String(128), nullable=True))
        batch.add_column(sa.Column("content_type", sa.String(32), nullable=True))
        batch.add_column(sa.Column("ocr_source", sa.String(128), nullable=True))
        batch.add_column(sa.Column("ocr_status", sa.String(32), nullable=True))
        batch.add_column(sa.Column("decision_source", sa.String(32), nullable=True))
        batch.add_column(sa.Column("analysis_reason", sa.Text(), nullable=True))
        batch.add_column(sa.Column("analysis_metadata", sa.JSON(), nullable=True))
        batch.create_index("ix_predictions_image_sha256", ["image_sha256"])
    # Fix the old interpretation of reviewed without manufacturing human labels.
    op.execute(sa.text("UPDATE predictions SET reviewed = FALSE WHERE human_verdict IS NULL"))


def downgrade():
    # Abstained rows legitimately have no score; do not invent scores to downgrade.
    with op.batch_alter_table("predictions") as batch:
        batch.drop_index("ix_predictions_image_sha256")
        for name in ["analysis_metadata", "analysis_reason", "decision_source", "ocr_status", "ocr_source", "content_type", "model_version", "image_sha256", "extracted_text"]:
            batch.drop_column(name)
