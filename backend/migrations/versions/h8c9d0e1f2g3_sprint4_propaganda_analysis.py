"""sprint4: propaganda columns + analysis_confidence on article_analysis

Revision ID: h8c9d0e1f2g3
Revises: g7b8c9d0e1f2
Create Date: 2026-06-20
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = 'h8c9d0e1f2g3'
down_revision = 'g7b8c9d0e1f2'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('article_analysis', sa.Column('propaganda_techniques', JSONB, nullable=True))
    op.add_column('article_analysis', sa.Column('propaganda_confidence', sa.Float, nullable=True))
    op.add_column('article_analysis', sa.Column('propaganda_targets', JSONB, nullable=True))
    op.add_column('article_analysis', sa.Column('analysis_confidence', sa.Float, nullable=True))

    op.create_index(
        'ix_article_analysis_propaganda',
        'article_analysis',
        [sa.text("(jsonb_array_length(propaganda_techniques))")],
        postgresql_where=sa.text("propaganda_techniques IS NOT NULL"),
    )


def downgrade():
    op.drop_index('ix_article_analysis_propaganda', table_name='article_analysis')
    op.drop_column('article_analysis', 'analysis_confidence')
    op.drop_column('article_analysis', 'propaganda_targets')
    op.drop_column('article_analysis', 'propaganda_confidence')
    op.drop_column('article_analysis', 'propaganda_techniques')
