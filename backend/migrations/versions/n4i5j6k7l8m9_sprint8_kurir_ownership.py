"""Sprint 8: ispravka vlasništva Kurir → Domaći privatni

Revision ID: n4i5j6k7l8m9
Revises: m3h4i5j6k7l8
Create Date: 2026-06-21
"""
from alembic import op
from sqlalchemy import text

revision = "n4i5j6k7l8m9"
down_revision = "m3h4i5j6k7l8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    # Kurir = Adria Media Group (Aleksandar Rodić) — domaći vlasnik, ne strani.
    conn.execute(text(
        "UPDATE sources SET owner = :owner, owner_group = :grp WHERE source_id = 'kurir'"
    ), {"owner": "Adria Media Group (Aleksandar Rodić)", "grp": "Domaći privatni"})


def downgrade() -> None:
    pass
