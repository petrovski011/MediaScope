"""Sprint 7: narrative_clusters — semantičko klasterovanje narativnih predloga

Revision ID: l2g3h4i5j6k7
Revises: k1f2g3h4i5j6
Create Date: 2026-06-20
"""
from alembic import op
import sqlalchemy as sa

revision = "l2g3h4i5j6k7"
down_revision = "k1f2g3h4i5j6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # Clusters table — each cluster = one semantic group of proposals
    op.create_table(
        "narrative_clusters",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("representative_name", sa.String(500), nullable=False),
        sa.Column("narrative_type", sa.String(50), nullable=False, server_default="thematic"),
        sa.Column("centroid_embedding", sa.Text, nullable=True),  # stored as vector via raw SQL
        sa.Column("proposal_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("accepted_narrative_id", sa.Integer, sa.ForeignKey("narratives.id"), nullable=True),
        sa.Column("first_seen", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("last_seen", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )

    # Fix: drop centroid_embedding as Text and recreate as vector(768) via raw SQL
    op.execute("ALTER TABLE narrative_clusters DROP COLUMN centroid_embedding")
    op.execute("ALTER TABLE narrative_clusters ADD COLUMN centroid_embedding vector(768)")

    # Add embedding + cluster_id to narrative_proposals
    op.execute("ALTER TABLE narrative_proposals ADD COLUMN IF NOT EXISTS embedding vector(768)")
    op.add_column("narrative_proposals", sa.Column("cluster_id", sa.BigInteger, sa.ForeignKey("narrative_clusters.id"), nullable=True))

    # Index for fast ANN search
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_narrative_clusters_embedding
        ON narrative_clusters USING ivfflat (centroid_embedding vector_cosine_ops)
        WITH (lists = 10)
    """)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_narrative_clusters_embedding")
    op.drop_column("narrative_proposals", "cluster_id")
    op.execute("ALTER TABLE narrative_proposals DROP COLUMN IF EXISTS embedding")
    op.drop_table("narrative_clusters")
