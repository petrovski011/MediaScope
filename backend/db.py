"""MediaScope SQLite storage layer.

DB file: data/mediascope.db (relative to the MediaScope project root).
Primary key is URL — re-inserting the same article updates it (upsert).
"""
from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime, timedelta
from typing import List, Optional

from scrapers.base import ArticleData

_DB_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data", "mediascope.db",
)

_CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS articles (
    url           TEXT PRIMARY KEY,
    source_id     TEXT NOT NULL,
    title         TEXT,
    subtitle      TEXT,
    text          TEXT,
    author        TEXT,
    published_at  TEXT,
    updated_at    TEXT,
    category      TEXT,
    tags          TEXT,
    image_url     TEXT,
    image_caption TEXT,
    comment_count INTEGER,
    content_hash  TEXT,
    scraped_at    TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_source   ON articles(source_id);
CREATE INDEX IF NOT EXISTS idx_pub      ON articles(published_at);
CREATE INDEX IF NOT EXISTS idx_scraped  ON articles(scraped_at);
"""


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(_DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Create tables if they don't exist."""
    with _connect() as conn:
        conn.executescript(_CREATE_TABLE)


def save_article(article: ArticleData) -> bool:
    """Insert or replace article. Returns True if it was new (INSERT), False if updated/skipped.

    Update policy:
    - New article → always INSERT.
    - Existing article, content changed (different hash) → full UPDATE.
    - Existing article, content unchanged but text is short (<200 chars) → full UPDATE so
      stale empty articles get refreshed when scraper improves.
    - Existing article, content unchanged and text is substantial → metadata-only UPDATE
      (tags, author, category, scraped_at) so fixes to those fields always land in DB.
    """
    with _connect() as conn:
        existing = conn.execute(
            "SELECT content_hash, text FROM articles WHERE url = ?", (article.url,)
        ).fetchone()

        is_new = existing is None
        tags_json = json.dumps(article.tags, ensure_ascii=False) if article.tags else "[]"
        scraped_iso = article.scraped_at.isoformat() if article.scraped_at else datetime.utcnow().isoformat()

        if is_new:
            # Brand-new article — full insert
            conn.execute(
                """
                INSERT INTO articles
                    (url, source_id, title, subtitle, text, author,
                     published_at, updated_at, category, tags,
                     image_url, image_caption, comment_count, content_hash, scraped_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    article.url, article.source_id, article.title, article.subtitle,
                    article.text, article.author,
                    article.published_at.isoformat() if article.published_at else None,
                    article.updated_at.isoformat() if article.updated_at else None,
                    article.category, tags_json,
                    article.image_url, article.image_caption, article.comment_count,
                    article.content_hash, scraped_iso,
                ),
            )
            return True

        existing_text = existing["text"] or ""
        same_hash = existing["content_hash"] == article.content_hash
        text_is_short = len(existing_text) < 200  # stale empty / very short text

        if same_hash and not text_is_short:
            # Content unchanged and article already has good text — metadata-only update.
            # This ensures tag/author fixes propagate even without a text change.
            conn.execute(
                """
                UPDATE articles
                SET author=?, category=?, tags=?, scraped_at=?
                WHERE url=?
                """,
                (article.author, article.category, tags_json, scraped_iso, article.url),
            )
            return False

        # Full update: content changed OR stale short text
        conn.execute(
            """
            UPDATE articles SET
                title=?, subtitle=?, text=?, author=?,
                published_at=?, updated_at=?, category=?, tags=?,
                image_url=?, image_caption=?, comment_count=?,
                content_hash=?, scraped_at=?
            WHERE url=?
            """,
            (
                article.title, article.subtitle, article.text, article.author,
                article.published_at.isoformat() if article.published_at else None,
                article.updated_at.isoformat() if article.updated_at else None,
                article.category, tags_json,
                article.image_url, article.image_caption, article.comment_count,
                article.content_hash, scraped_iso,
                article.url,
            ),
        )
        return False


def get_stats(hours: int = 24) -> List[dict]:
    """Return per-source article count for the last N hours."""
    since = (datetime.utcnow() - timedelta(hours=hours)).isoformat()
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT source_id, COUNT(*) as count
            FROM articles
            WHERE scraped_at >= ?
            GROUP BY source_id
            ORDER BY count DESC
            """,
            (since,),
        ).fetchall()
    return [dict(r) for r in rows]


def get_total() -> int:
    with _connect() as conn:
        return conn.execute("SELECT COUNT(*) FROM articles").fetchone()[0]


def get_recent(source_id: Optional[str] = None, hours: int = 24, limit: int = 10) -> List[dict]:
    """Return recent articles, optionally filtered by source."""
    since = (datetime.utcnow() - timedelta(hours=hours)).isoformat()
    with _connect() as conn:
        if source_id:
            rows = conn.execute(
                "SELECT url, source_id, title, published_at, category FROM articles "
                "WHERE source_id = ? AND scraped_at >= ? ORDER BY published_at DESC LIMIT ?",
                (source_id, since, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT url, source_id, title, published_at, category FROM articles "
                "WHERE scraped_at >= ? ORDER BY published_at DESC LIMIT ?",
                (since, limit),
            ).fetchall()
    return [dict(r) for r in rows]
