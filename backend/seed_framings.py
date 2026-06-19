"""Seed skripta za framing_types tabelu. Pokretati jednokratno.

docker compose exec backend python seed_framings.py
"""
import asyncio
import asyncpg
from config import settings

FRAMING_TYPES = [
    ("threat_frame",    "Okvir pretnje — tematizuje opasnost, krizu, napad na Srbiju ili institucije"),
    ("conflict_frame",  "Okvir sukoba — suprotstavlja aktere (vlast vs opozicija, Srbija vs Zapad)"),
    ("victim_frame",    "Okvir žrtve — neko trpi posledice tuđih odluka ili nepravde"),
    ("progress_frame",  "Okvir napretka — ističe uspehe, reforme, razvoj, pobede"),
    ("morality_frame",  "Moralni okvir — etički sud, patriotizam, tradicija, dužnost"),
]

async def main():
    dsn = settings.DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")
    pg = await asyncpg.connect(dsn)
    try:
        for name, desc in FRAMING_TYPES:
            existing = await pg.fetchval(
                "SELECT id FROM framing_types WHERE name = $1", name
            )
            if existing:
                print(f"  Već postoji: {name}")
                continue
            await pg.execute(
                "INSERT INTO framing_types (name, description, is_validated) VALUES ($1, $2, TRUE)",
                name, desc,
            )
            print(f"  Dodato: {name}")
        rows = await pg.fetch("SELECT id, name FROM framing_types ORDER BY id")
        print(f"\nUkupno u framing_types: {len(rows)}")
        for r in rows:
            print(f"  {r['id']}: {r['name']}")
    finally:
        await pg.close()

asyncio.run(main())
