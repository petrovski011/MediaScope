"""A2: geopolitical_sentiment JSONB kolona u article_analysis

Revision ID: r8s9t0u1v2w3
Revises: q7m8n9o0p1q2
Create Date: 2026-06-22
"""
from alembic import op

revision = "r8s9t0u1v2w3"
down_revision = "q7m8n9o0p1q2"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
        ALTER TABLE article_analysis
        ADD COLUMN IF NOT EXISTS geopolitical_sentiment JSONB
    """)


def downgrade():
    op.execute("""
        ALTER TABLE article_analysis
        DROP COLUMN IF EXISTS geopolitical_sentiment
    """)
