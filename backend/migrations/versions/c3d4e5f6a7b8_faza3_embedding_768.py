"""Faza 3: migracija article_embeddings.embedding na vector(768) za lokalni e5-base

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-06-20

Kolona je prazna (0 redova) pa je bezbedno drop+recreate. Lokalni model
intfloat/multilingual-e5-base ima 768 dimenzija (umesto 1536 iz prvobitne sheme).
"""
from alembic import op

revision = "c3d4e5f6a7b8"
down_revision = "b2c3d4e5f6a7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_embeddings_vector")
    op.execute("ALTER TABLE article_embeddings DROP COLUMN IF EXISTS embedding")
    op.execute("ALTER TABLE article_embeddings ADD COLUMN embedding vector(768)")
    op.execute(
        "CREATE INDEX idx_embeddings_vector ON article_embeddings "
        "USING hnsw (embedding vector_cosine_ops)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_embeddings_vector")
    op.execute("ALTER TABLE article_embeddings DROP COLUMN IF EXISTS embedding")
    op.execute("ALTER TABLE article_embeddings ADD COLUMN embedding vector(1536)")
    op.execute(
        "CREATE INDEX idx_embeddings_vector ON article_embeddings "
        "USING hnsw (embedding vector_cosine_ops)"
    )
