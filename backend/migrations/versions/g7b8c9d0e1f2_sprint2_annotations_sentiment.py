"""Sprint 2: annotations (is_private, updated_at) + article_entities sentiment + researcher_actions

Revision ID: g7b8c9d0e1f2
Revises: f6a7b8c9d0e1
Create Date: 2026-06-20
"""
from alembic import op
import sqlalchemy as sa

revision = "g7b8c9d0e1f2"
down_revision = "f6a7b8c9d0e1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Annotations: dodati is_private i updated_at
    op.add_column("annotations", sa.Column("is_private", sa.Boolean(), nullable=False, server_default="FALSE"))
    op.add_column("annotations", sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True))

    # 2. Article entities: dodati sentiment po pominjanju akteru (-1..1)
    op.add_column("article_entities", sa.Column("sentiment", sa.Float(), nullable=True))

    # 3. Researcher actions (activity log)
    op.create_table(
        "researcher_actions",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("action_type", sa.String(50), nullable=False),
        sa.Column("entity_type", sa.String(50), nullable=False),
        sa.Column("entity_id", sa.BigInteger(), nullable=True),
        sa.Column("old_status", sa.String(100), nullable=True),
        sa.Column("new_status", sa.String(100), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("reverted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("idx_researcher_actions_user", "researcher_actions", ["user_id"])
    op.create_index("idx_researcher_actions_type", "researcher_actions", ["action_type"])
    op.create_index("idx_researcher_actions_created", "researcher_actions", ["created_at"])


def downgrade() -> None:
    op.drop_table("researcher_actions")
    op.drop_column("article_entities", "sentiment")
    op.drop_column("annotations", "updated_at")
    op.drop_column("annotations", "is_private")
