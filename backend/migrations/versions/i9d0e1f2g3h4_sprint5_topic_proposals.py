"""Sprint 5: topic_proposals tabela za NOVA_TEMA predloge iz AI pipeline-a

Revision ID: i9d0e1f2g3h4
Revises: h8c9d0e1f2g3
Create Date: 2026-06-20
"""
from alembic import op
import sqlalchemy as sa

revision = "i9d0e1f2g3h4"
down_revision = "h8c9d0e1f2g3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "topic_proposals",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("proposed_key", sa.String(100), nullable=False),
        sa.Column("article_count", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("first_seen", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("last_seen", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("accepted_topic_id", sa.Integer(), sa.ForeignKey("topics.id"), nullable=True),
    )
    op.create_index("idx_topic_proposals_status", "topic_proposals", ["status"])
    # Partial unique index: samo jedan pending red po proposed_key
    op.execute(
        "CREATE UNIQUE INDEX idx_topic_proposals_pending_key "
        "ON topic_proposals(proposed_key) WHERE status = 'pending'"
    )


def downgrade() -> None:
    op.drop_index("idx_topic_proposals_pending_key", table_name="topic_proposals")
    op.drop_index("idx_topic_proposals_status", table_name="topic_proposals")
    op.drop_table("topic_proposals")
