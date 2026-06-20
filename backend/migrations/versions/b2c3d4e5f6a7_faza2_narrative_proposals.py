"""Faza 2: narrative_proposals staging tabela

Revision ID: b2c3d4e5f6a7
Revises: a1f1c2d3e4f5
Create Date: 2026-06-20

Rucno pisana migracija.
"""
from alembic import op
import sqlalchemy as sa

revision = "b2c3d4e5f6a7"
down_revision = "a1f1c2d3e4f5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "narrative_proposals",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(300), nullable=False),
        sa.Column("narrative_type", sa.String(20), nullable=False, server_default="thematic"),
        sa.Column("description", sa.Text()),
        sa.Column("supporting_text", sa.Text()),
        sa.Column("article_id", sa.BigInteger(), sa.ForeignKey("articles.id")),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("occurrences", sa.Integer(), server_default="1"),
        sa.Column("reviewed_by", sa.Integer(), sa.ForeignKey("users.id")),
        sa.Column("reviewed_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("idx_narrative_proposals_status", "narrative_proposals", ["status"])


def downgrade() -> None:
    op.drop_index("idx_narrative_proposals_status", table_name="narrative_proposals")
    op.drop_table("narrative_proposals")
