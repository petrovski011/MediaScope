"""Sprint 6: ispravke vlasnistva — owner_group standardizacija

Revision ID: k1f2g3h4i5j6
Revises: j0e1f2g3h4i5
Create Date: 2026-06-20
"""
from alembic import op
from sqlalchemy import text

revision = "k1f2g3h4i5j6"
down_revision = "j0e1f2g3h4i5"
branch_labels = None
depends_on = None

CORRECTIONS = [
    # Adria News Network — owner se skracuje na "United Media"
    ("n1",       "United Media", "Adria News Network"),
    ("nova",     "United Media", "Adria News Network"),
    ("danas",    "United Media", "Adria News Network"),
    ("radar",    "United Media", "Adria News Network"),
    # "Privatni srpski" → "Domaći privatni" (standardizacija)
    ("tanjug",   "Tačno d.o.o. (RTV Pančevo 60%, Minacord/Joksimović 40%)", "Domaći privatni"),
    ("telegraf", "Veselin Jevrosimović", "Domaći privatni"),
    # Srbija danas
    ("sd",       "Goran Lalić", "Domaći privatni"),
]


def upgrade() -> None:
    conn = op.get_bind()
    for source_id, owner, owner_group in CORRECTIONS:
        conn.execute(
            text("UPDATE sources SET owner = :owner, owner_group = :owner_group WHERE source_id = :source_id"),
            {"owner": owner, "owner_group": owner_group, "source_id": source_id},
        )
    # Standardizacija dijakritike za starije redove
    conn.execute(text("UPDATE sources SET owner_group = 'Domaći privatni' WHERE owner_group = 'Domaci privatni'"))


def downgrade() -> None:
    pass
