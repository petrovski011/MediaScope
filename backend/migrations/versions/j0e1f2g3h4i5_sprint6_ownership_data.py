"""Sprint 6: vlasnistvo medija — podatkovna migracija

Revision ID: j0e1f2g3h4i5
Revises: i9d0e1f2g3h4
Create Date: 2026-06-20
"""
from alembic import op
from sqlalchemy import text

revision = "j0e1f2g3h4i5"
down_revision = "i9d0e1f2g3h4"
branch_labels = None
depends_on = None

UPDATES = [
    ("b92",      "Kopernikus Corporation (Srđan Milovanović)", "Kopernikus Media",  "Kupljeno od United Media 2018. Srdan Milovanovic, Cyprus-registered Kopernikus Corp."),
    ("prva",     "Kopernikus Corporation (Srđan Milovanović)", "Kopernikus Media",  "Isti vlasnik kao B92. Kopernikus Corp, Cyprus."),
    ("n1",       "United Media",                               "Adria News Network", "United Media (rebranding u Adria News Network feb 2026). Prodaja Alpac Capital u toku."),
    ("nova",     "United Media",                               "Adria News Network", "United Media (rebranding u Adria News Network feb 2026). Prodaja Alpac Capital u toku."),
    ("danas",    "United Media",                               "Adria News Network", "United Media (rebranding u Adria News Network feb 2026). Prodaja Alpac Capital u toku."),
    ("radar",    "United Media",                               "Adria News Network", "United Media (rebranding u Adria News Network feb 2026). Prodaja Alpac Capital u toku."),
    ("tanjug",   "Tačno d.o.o. (RTV Pančevo 60%, Minacord/Joksimović 40%)", "Domaći privatni", "Privatizovan 2021. Finansiranje delimicno iz javnih fondova — state-adjacent."),
    ("telegraf", "Veselin Jevrosimović",                       "Domaći privatni",   "Pouzdanost: srednja. Tabloidan portal sa pro-vladinskom urednickom linijom."),
    ("sd",       "Goran Lalić",                                "Domaći privatni",   "Srbija danas — pro-vladinski portal."),
]


def upgrade() -> None:
    conn = op.get_bind()
    for source_id, owner, owner_group, notes in UPDATES:
        conn.execute(
            text(
                "UPDATE sources SET owner = :owner, owner_group = :owner_group, "
                "notes = COALESCE(notes || ' | ', '') || :notes "
                "WHERE source_id = :source_id"
            ),
            {"owner": owner, "owner_group": owner_group, "notes": notes, "source_id": source_id},
        )


def downgrade() -> None:
    pass
