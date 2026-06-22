"""A4: narrative_origin_tracking tabela

Revision ID: s9t0u1v2w3x4
Revises: r8s9t0u1v2w3
Create Date: 2026-06-22
"""
from alembic import op

revision = "s9t0u1v2w3x4"
down_revision = "r8s9t0u1v2w3"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
        CREATE TABLE IF NOT EXISTS narrative_origin_tracking (
            id BIGSERIAL PRIMARY KEY,
            narrative_id BIGINT NOT NULL UNIQUE,
            first_source_id TEXT,
            first_published_at TIMESTAMPTZ,
            has_exact_time BOOLEAN DEFAULT TRUE,
            total_sources INT,
            spread_hours FLOAT,
            spread JSONB,
            window_days INT DEFAULT 14,
            computed_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_narrative_origin_narrative ON narrative_origin_tracking (narrative_id)")


def downgrade():
    op.execute("DROP TABLE IF EXISTS narrative_origin_tracking")
