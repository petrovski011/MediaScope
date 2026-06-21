"""Sprint 8: framing_type_proposals — embedding vector(768) za semantički matching

Revision ID: p6k7l8m9n0o1
Revises: o5j6k7l8m9n0
Create Date: 2026-06-21
"""
from alembic import op

revision = "p6k7l8m9n0o1"
down_revision = "o5j6k7l8m9n0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE framing_type_proposals ADD COLUMN IF NOT EXISTS embedding vector(768)")
    # Index za brze cosine pretrage po embeddingu
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_framing_proposals_embedding
        ON framing_type_proposals USING ivfflat (embedding vector_cosine_ops)
        WHERE status = 'pending' AND embedding IS NOT NULL
    """)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_framing_proposals_embedding")
    op.execute("ALTER TABLE framing_type_proposals DROP COLUMN IF EXISTS embedding")
