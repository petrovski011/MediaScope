"""
Backfill published_at timestamps za postojece clanke u bazi.

- Tanjug: svaki clanak ima article:published_time meta tag — re-fetchujemo i upisujemo.
- RTS:    article stranice NEMAJU meta tag; jedino RSS daje timestamps ali samo za
          poslednjih ~20 clanaka. Stari RTS clanci ostaju NULL.

Pokretanje:
    docker compose exec backend python scripts/backfill_timestamps.py
    docker compose exec backend python scripts/backfill_timestamps.py --dry-run
"""
from __future__ import annotations

import argparse
import logging
import sys
import time
from datetime import datetime
from typing import Optional

import psycopg2
import requests
from bs4 import BeautifulSoup

sys.path.insert(0, "/app")
from scrapers.utils import parse_sr_date

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("backfill")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )
}


def get_tanjug_timestamp(url: str) -> Optional[datetime]:
    try:
        r = requests.get(url, headers=HEADERS, timeout=12, allow_redirects=True)
        if r.status_code != 200:
            return None
        soup = BeautifulSoup(r.content, "lxml")
        og = soup.find("meta", property="article:published_time")
        if og and og.get("content"):
            return parse_sr_date(og["content"])
    except Exception as exc:
        log.warning("fetch error %s: %s", url, exc)
    return None


def run(dry_run: bool = False):
    import os
    dsn = os.environ.get(
        "DATABASE_URL",
        "postgresql://mediascope:mediascope@postgres:5432/mediascope",
    )
    # SQLAlchemy async DSN koristi postgresql+asyncpg:// — psycopg2 treba postgresql://
    dsn = dsn.replace("postgresql+asyncpg://", "postgresql://")

    conn = psycopg2.connect(dsn)
    cur = conn.cursor()

    # Ucitaj sve Tanjug clanke bez published_at ili sa midnight timestamp
    cur.execute("""
        SELECT id, url
        FROM articles
        WHERE source_id = 'tanjug'
          AND (
            published_at IS NULL
            OR (EXTRACT(hour FROM published_at) = 0 AND EXTRACT(minute FROM published_at) = 0)
          )
        ORDER BY id
    """)
    rows = cur.fetchall()
    log.info("Tanjug clanaka za backfill: %d", len(rows))

    updated = 0
    failed = 0
    skipped = 0

    for i, (article_id, url) in enumerate(rows, 1):
        log.info("[%d/%d] %s", i, len(rows), url[-70:])
        ts = get_tanjug_timestamp(url)
        if ts:
            log.info("  -> %s", ts)
            if not dry_run:
                cur.execute(
                    "UPDATE articles SET published_at = %s WHERE id = %s",
                    (ts, article_id),
                )
                conn.commit()
            updated += 1
        else:
            log.warning("  -> timestamp nije nadjen")
            failed += 1

        # Pauza da ne preopteretimo Tanjug server
        if i % 10 == 0:
            time.sleep(2)
        else:
            time.sleep(0.3)

    cur.close()
    conn.close()

    log.info("")
    log.info("=== Gotovo ===")
    log.info("Azurirano: %d", updated)
    log.info("Nije nadjen timestamp: %d", failed)
    if dry_run:
        log.info("(DRY RUN — nista nije upisano u bazu)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="Samo ispisi, ne upisuj")
    args = parser.parse_args()
    run(dry_run=args.dry_run)
