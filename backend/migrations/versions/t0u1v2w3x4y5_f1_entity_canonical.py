"""F1: entity canonical_id za aliasing/merging aktera

Revision ID: t0u1v2w3x4y5
Revises: s9t0u1v2w3x4
Create Date: 2026-06-22
"""

from alembic import op
import sqlalchemy as sa

revision = 't0u1v2w3x4y5'
down_revision = 's9t0u1v2w3x4'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('entities', sa.Column('canonical_id', sa.BigInteger(), nullable=True))
    op.create_foreign_key(
        'fk_entities_canonical_id', 'entities', 'entities',
        ['canonical_id'], ['id'], ondelete='SET NULL'
    )
    op.create_index('ix_entities_canonical_id', 'entities', ['canonical_id'])


def downgrade():
    op.drop_index('ix_entities_canonical_id', 'entities')
    op.drop_constraint('fk_entities_canonical_id', 'entities', type_='foreignkey')
    op.drop_column('entities', 'canonical_id')
