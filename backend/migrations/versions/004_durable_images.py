"""Keep training images in Supabase even when deployment files are ephemeral."""
from alembic import op
import sqlalchemy as sa

revision = "004"
down_revision = "003"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("meme_images",
        sa.Column("sha256", sa.String(64), primary_key=True),
        sa.Column("content_type", sa.String(64), nullable=False),
        sa.Column("content", sa.LargeBinary(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade():
    op.drop_table("meme_images")
