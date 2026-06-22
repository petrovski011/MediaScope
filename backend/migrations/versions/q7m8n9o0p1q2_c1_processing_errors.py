"""C1: processing_errors — per-article pipeline greške

Revision ID: q7m8n9o0p1q2
Revises: p6k7l8m9n0o1
Create Date: 2026-06-22
"""
from alembic import op

revision = "q7m8n9o0p1q2"
down_revision = "p6k7l8m9n0o1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS processing_errors (
            id BIGSERIAL PRIMARY KEY,
            article_id BIGINT,
            batch_id TEXT,
            stage VARCHAR(50),
            error_type VARCHAR(100),
            error_message TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_processing_errors_batch ON processing_errors (batch_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_processing_errors_article ON processing_errors (article_id)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_processing_errors_article")
    op.execute("DROP INDEX IF EXISTS idx_processing_errors_batch")
    op.execute("DROP TABLE IF EXISTS processing_errors")
