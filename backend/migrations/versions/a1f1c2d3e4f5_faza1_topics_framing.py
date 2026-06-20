"""Faza 1: topics tabela + framing_type_proposals + unique indeksi za tematski framing

Revision ID: a1f1c2d3e4f5
Revises: 6b29a6f24c92
Create Date: 2026-06-20

Rucno pisana migracija (NE autogenerate — autogenerate bi pokusao DROP
embeddings/calibration/origin/watchlist tabela jer modeli ne deklarisu SQL indekse).
"""
from alembic import op
import sqlalchemy as sa

revision = "a1f1c2d3e4f5"
down_revision = "6b29a6f24c92"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. topics tabela
    op.create_table(
        "topics",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("key", sa.String(50), nullable=False, unique=True),
        sa.Column("label_sr", sa.String(200), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # 2. framing_type_proposals staging tabela
    op.create_table(
        "framing_type_proposals",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("topic_id", sa.Integer(), sa.ForeignKey("topics.id")),
        sa.Column("description", sa.Text()),
        sa.Column("supporting_text", sa.Text()),
        sa.Column("article_id", sa.BigInteger(), sa.ForeignKey("articles.id")),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("occurrences", sa.Integer(), server_default="1"),
        sa.Column("reviewed_by", sa.Integer(), sa.ForeignKey("users.id")),
        sa.Column("reviewed_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("idx_framing_proposals_status", "framing_type_proposals", ["status"])

    # 3. Unique indeksi na framing_types — odvojeno za globalne (topic_id NULL) i tematske,
    #    jer Postgres tretira NULL kao razlicit u obicnom UNIQUE constraint-u.
    op.create_index(
        "uq_framing_types_global", "framing_types", ["name"],
        unique=True, postgresql_where=sa.text("topic_id IS NULL"),
    )
    op.create_index(
        "uq_framing_types_topic", "framing_types", ["name", "topic_id"],
        unique=True, postgresql_where=sa.text("topic_id IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_framing_types_topic", table_name="framing_types")
    op.drop_index("uq_framing_types_global", table_name="framing_types")
    op.drop_index("idx_framing_proposals_status", table_name="framing_type_proposals")
    op.drop_table("framing_type_proposals")
    op.drop_table("topics")
