#!/usr/bin/env python3
"""
Migrates articles from the SQLite scraper DB into PostgreSQL.

Usage:
    python3 scripts/migrate_sqlite_to_pg.py

Requires PostgreSQL to be running (docker compose up -d postgres).
Reads from data/mediascope.db, writes to the DATABASE_URL in .env.
"""

import asyncio
import hashlib
import json
import os
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import asyncpg
from dotenv import load_dotenv

ROOT = Path(__file__).parent.parent
load_dotenv(ROOT / ".env")

SQLITE_PATH = ROOT / "data" / "mediascope.db"
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://mediascope:devpassword@localhost:5432/mediascope",
)
# asyncpg uses postgresql://, not postgresql+asyncpg://
PG_DSN = DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")


def _url_hash(url: str) -> str:
    return hashlib.sha256(url.encode()).hexdigest()


def _content_hash(title: str, text: str) -> str:
    return hashlib.sha256(f"{title or ''}{text or ''}".encode()).hexdigest()


def _parse_ts(ts_str: Optional[str]) -> Optional[datetime]:
    if not ts_str:
        return None
    for fmt in ("%Y-%m-%dT%H:%M:%S.%f%z", "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%S"):
        try:
            dt = datetime.strptime(ts_str, fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except ValueError:
            continue
    return None


async def main():
    if not SQLITE_PATH.exists():
        print(f"ERROR: SQLite DB not found at {SQLITE_PATH}")
        sys.exit(1)

    sqlite_conn = sqlite3.connect(str(SQLITE_PATH))
    sqlite_conn.row_factory = sqlite3.Row
    rows = sqlite_conn.execute(
        "SELECT * FROM articles ORDER BY scraped_at"
    ).fetchall()
    sqlite_conn.close()

    print(f"Found {len(rows)} articles in SQLite.")

    pg = await asyncpg.connect(PG_DSN)

    # Check which URLs already exist
    existing = set(
        r["url_hash"]
        for r in await pg.fetch("SELECT url_hash FROM articles")
    )
    print(f"PostgreSQL already has {len(existing)} articles.")

    inserted = 0
    skipped = 0
    errors = 0

    for row in rows:
        url = row["url"]
        uh = _url_hash(url)

        if uh in existing:
            skipped += 1
            continue

        title = (row["title"] or "")[:500]
        text = row["text"] or ""
        category = (row["category"] or "")[:200] or None
        tags_raw = row["tags"] or "[]"
        try:
            tags = json.loads(tags_raw) if isinstance(tags_raw, str) else tags_raw
        except Exception:
            tags = []

        try:
            await pg.execute(
                """
                INSERT INTO articles (
                    source_id, url, url_hash, content_hash, version,
                    title, subtitle, text_content, word_count,
                    author, published_at, updated_at, category, tags,
                    image_url, image_caption, comment_count,
                    scraped_at, has_paywall, is_live_blog, language, script
                ) VALUES (
                    $1, $2, $3, $4, 1,
                    $5, $6, $7, $8,
                    $9, $10, $11, $12, $13,
                    $14, $15, $16,
                    $17, false, false, 'sr', 'Latn'
                )
                ON CONFLICT (url_hash) DO NOTHING
                """,
                row["source_id"],
                url,
                uh,
                _content_hash(title, text),
                title,
                row["subtitle"],
                text if text else None,
                len(text.split()) if text else 0,
                row["author"],
                _parse_ts(row["published_at"]),
                _parse_ts(row["updated_at"]),
                category,
                tags if tags else None,
                row["image_url"],
                row["image_caption"],
                row["comment_count"],
                _parse_ts(row["scraped_at"]) or datetime.now(timezone.utc),
            )
            inserted += 1
            existing.add(uh)
        except Exception as e:
            print(f"  ERROR inserting {url[:80]}: {e}")
            errors += 1

        if (inserted + skipped) % 200 == 0:
            print(f"  Progress: {inserted} inserted, {skipped} skipped, {errors} errors")

    await pg.close()

    print(f"\nDone. Inserted: {inserted} | Skipped: {skipped} | Errors: {errors}")


if __name__ == "__main__":
    asyncio.run(main())
