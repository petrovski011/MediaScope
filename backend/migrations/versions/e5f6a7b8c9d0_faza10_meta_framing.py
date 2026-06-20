"""Faza 10: meta-framing kolone (narod vs elite) u article_analysis

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-06-20
"""
from alembic import op
import sqlalchemy as sa

revision = "e5f6a7b8c9d0"
down_revision = "d4e5f6a7b8c9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("article_analysis", sa.Column("populist_framing", sa.Boolean(), server_default=sa.false()))
    op.add_column("article_analysis", sa.Column("populist_confidence", sa.Float()))


def downgrade() -> None:
    op.drop_column("article_analysis", "populist_confidence")
    op.drop_column("article_analysis", "populist_framing")
