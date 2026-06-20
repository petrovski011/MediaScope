"""Faza 6: period_types tabela (kontekstualizacija anomalija)

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-06-20
"""
from alembic import op
import sqlalchemy as sa

revision = "d4e5f6a7b8c9"
down_revision = "c3d4e5f6a7b8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "period_types",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("date_from", sa.String(10), nullable=False),
        sa.Column("date_to", sa.String(10), nullable=False),
        sa.Column("period_type", sa.String(20), nullable=False),
        sa.Column("note", sa.Text()),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("period_types")
