"""Sprint 8: framing_type_proposals — dodaj article_ids[] za tracking svih clanaka po predlogu

Revision ID: o5j6k7l8m9n0
Revises: n4i5j6k7l8m9
Create Date: 2026-06-21
"""
from alembic import op

revision = "o5j6k7l8m9n0"
down_revision = "n4i5j6k7l8m9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE framing_type_proposals
        ADD COLUMN IF NOT EXISTS article_ids bigint[] NOT NULL DEFAULT '{}'
    """)
    # Popuni postojeće redove: article_id koji vec postoji ide u niz
    op.execute("""
        UPDATE framing_type_proposals
        SET article_ids = ARRAY[article_id]
        WHERE article_id IS NOT NULL AND article_ids = '{}'
    """)


def downgrade() -> None:
    op.execute("ALTER TABLE framing_type_proposals DROP COLUMN IF EXISTS article_ids")
