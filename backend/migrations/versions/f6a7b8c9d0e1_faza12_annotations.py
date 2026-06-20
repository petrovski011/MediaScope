"""Faza 12: annotations tabela (beleske istrazivaca)

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-06-20
"""
from alembic import op
import sqlalchemy as sa

revision = "f6a7b8c9d0e1"
down_revision = "e5f6a7b8c9d0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "annotations",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("article_id", sa.BigInteger(), sa.ForeignKey("articles.id"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("idx_annotations_article", "annotations", ["article_id"])


def downgrade() -> None:
    op.drop_index("idx_annotations_article", table_name="annotations")
    op.drop_table("annotations")
