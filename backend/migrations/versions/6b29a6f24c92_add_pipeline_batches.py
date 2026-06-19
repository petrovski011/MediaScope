"""add_pipeline_batches

Revision ID: 6b29a6f24c92
Revises: e6eff05803a7
Create Date: 2026-06-20

"""
from alembic import op
import sqlalchemy as sa

revision = '6b29a6f24c92'
down_revision = 'e6eff05803a7'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'pipeline_batches',
        sa.Column('id', sa.BigInteger(), primary_key=True),
        sa.Column('batch_id', sa.Text(), nullable=False, unique=True),
        sa.Column('batch_type', sa.String(20), nullable=False, server_default='nightly'),
        sa.Column('batch_date', sa.String(20)),
        sa.Column('status', sa.String(20), nullable=False, server_default='submitted'),
        sa.Column('article_count', sa.Integer(), server_default='0'),
        sa.Column('articles_saved', sa.Integer(), server_default='0'),
        sa.Column('articles_failed', sa.Integer(), server_default='0'),
        sa.Column('submitted_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('finished_at', sa.DateTime(timezone=True)),
        sa.Column('error_message', sa.Text()),
    )


def downgrade() -> None:
    op.drop_table('pipeline_batches')
