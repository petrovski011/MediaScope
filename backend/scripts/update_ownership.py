"""
Azurira vlasnicke podatke za izvore na osnovu istrazivanja (jun 2026).

Kljucne izmene:
- B92: United Media → Kopernikus Media (Srdan Milovanovic, kupljeno 2018)
- Prva: United Media → Kopernikus Media (isti vlasnik kao B92)
- N1, Nova S, Danas, Radar: United Media → Adria News Network (rebranding feb 2026, prodaja Alpac Capital pending)
- Tanjug: Drzavni → privatizovan 2021, Tacno d.o.o. (state-adjacent finansiranje)
- Telegraf: Nezavisan → Veselin Jevrosimovic

Pokretanje:
    docker compose exec backend python scripts/update_ownership.py
    docker compose exec backend python scripts/update_ownership.py --dry-run
"""
from __future__ import annotations

import argparse
import logging
import os
import sys

import psycopg2

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger("update_ownership")

UPDATES = [
    # (source_id, owner, owner_group, notes)
    (
        "b92",
        "Kopernikus Corporation (Srđan Milovanović)",
        "Kopernikus Media",
        "Kupljeno od United Media 2018. Srdan Milovanovic, Cyprus-registered Kopernikus Corp.",
    ),
    (
        "prva",
        "Kopernikus Corporation (Srđan Milovanović)",
        "Kopernikus Media",
        "Isti vlasnik kao B92. Kopernikus Corp, Cyprus.",
    ),
    (
        "n1",
        "Adria News Network (United Group → Alpac Capital, pending H2 2026)",
        "Adria News Network",
        "United Media rebranded u Adria News Network feb 2026. Prodaja Alpac Capital u toku.",
    ),
    (
        "nova",
        "Adria News Network (United Group → Alpac Capital, pending H2 2026)",
        "Adria News Network",
        "United Media rebranded u Adria News Network feb 2026. Prodaja Alpac Capital u toku.",
    ),
    (
        "danas",
        "Adria News Network (United Group → Alpac Capital, pending H2 2026)",
        "Adria News Network",
        "United Media rebranded u Adria News Network feb 2026. Prodaja Alpac Capital u toku.",
    ),
    (
        "radar",
        "Adria News Network (United Group → Alpac Capital, pending H2 2026)",
        "Adria News Network",
        "United Media rebranded u Adria News Network feb 2026. Prodaja Alpac Capital u toku.",
    ),
    (
        "tanjug",
        "Tačno d.o.o. (RTV Pančevo 60%, Minacord/Joksimović 40%)",
        "Privatni srpski",
        "Privatizovan 2021. Finansiranje delimicno iz javnih fondova — state-adjacent.",
    ),
    (
        "telegraf",
        "Veselin Jevrosimović",
        "Privatni srpski",
        "Pouzdanost: srednja. Tabloidan portal sa pro-vladinskom urednickom linijom.",
    ),
]


def run(dry_run: bool = False):
    dsn = os.environ.get(
        "DATABASE_URL",
        "postgresql://mediascope:mediascope@postgres:5432/mediascope",
    )
    dsn = dsn.replace("postgresql+asyncpg://", "postgresql://")

    conn = psycopg2.connect(dsn)
    cur = conn.cursor()

    cur.execute("SELECT source_id, name, owner, owner_group FROM sources")
    existing = {r[0]: (r[1], r[2], r[3]) for r in cur.fetchall()}

    for source_id, owner, owner_group, notes in UPDATES:
        if source_id not in existing:
            log.warning("Izvor '%s' ne postoji u bazi — preskacam", source_id)
            continue

        name, old_owner, old_group = existing[source_id]
        log.info(
            "[%s] %s: '%s' / '%s' → '%s' / '%s'",
            source_id, name, old_owner, old_group, owner, owner_group,
        )

        if not dry_run:
            cur.execute(
                "UPDATE sources SET owner = %s, owner_group = %s, notes = COALESCE(notes || ' | ', '') || %s WHERE source_id = %s",
                (owner, owner_group, notes, source_id),
            )

    if not dry_run:
        conn.commit()
        log.info("Commit uspešan.")
    else:
        log.info("DRY RUN — nista nije upisano.")

    cur.close()
    conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    run(dry_run=args.dry_run)
