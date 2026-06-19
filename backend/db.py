"""MediaScope PostgreSQL storage layer za scraper.

Koristi psycopg2 (sync) za direktan upis u PostgreSQL.
Isti interfejs kao prethodni SQLite layer: init_db(), save_article().
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
from datetime import datetime, timedelta
from typing import List, Optional

import psycopg2
import psycopg2.extras

from scrapers.base import ArticleData

logger = logging.getLogger(__name__)

_DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql+asyncpg://mediascope:devpassword@localhost:5432/mediascope",
).replace("postgresql+asyncpg://", "postgresql://")


def _connect():
    return psycopg2.connect(_DATABASE_URL)


def _url_hash(url: str) -> str:
    return hashlib.sha256(url.encode("utf-8")).hexdigest()


def init_db() -> None:
    """Ništa za inicijalizaciju — PostgreSQL šema se kreira iz SQL fajla."""
    pass


def save_article(article: ArticleData) -> bool:
    """Upiši ili ažuriraj članak u PostgreSQL. Vraća True ako je novi."""
    url_hash = _url_hash(article.url)
    tags = article.tags or []
    schema_data = json.dumps(article.schema_data) if article.schema_data else None

    try:
        with _connect() as conn:
            with conn.cursor() as cur:
                # Provjeri da li postoji
                cur.execute(
                    "SELECT id, content_hash, length(text_content) FROM articles WHERE url_hash = %s",
                    (url_hash,),
                )
                existing = cur.fetchone()

                if existing is None:
                    # Novi članak
                    cur.execute(
                        """
                        INSERT INTO articles (
                            source_id, url, url_hash, content_hash, version,
                            title, subtitle, text_content, text_raw, word_count,
                            author, published_at, updated_at, category, tags,
                            image_url, image_caption, comment_count,
                            scraped_at, schema_data
                        ) VALUES (
                            %s,%s,%s,%s,1,
                            %s,%s,%s,%s,%s,
                            %s,%s,%s,%s,%s,
                            %s,%s,%s,
                            NOW(),%s
                        )
                        """,
                        (
                            article.source_id, article.url, url_hash, article.content_hash,
                            article.title, article.subtitle, article.text, article.text_raw,
                            len(article.text) if article.text else 0,
                            article.author, article.published_at, article.updated_at,
                            article.category, tags,
                            article.image_url, article.image_caption, article.comment_count,
                            schema_data,
                        ),
                    )
                    conn.commit()
                    return True

                # Postojeći članak
                existing_id, existing_hash, existing_text_len = existing
                same_hash = existing_hash == article.content_hash
                text_is_short = (existing_text_len or 0) < 200

                if same_hash and not text_is_short:
                    # Metadata update — uključi published_at ako je sad dostupan
                    cur.execute(
                        """
                        UPDATE articles SET author=%s, category=%s, tags=%s, scraped_at=NOW(),
                            published_at=COALESCE(published_at, %s)
                        WHERE id=%s
                        """,
                        (article.author, article.category, tags, article.published_at, existing_id),
                    )
                else:
                    # Pun update
                    cur.execute(
                        """
                        UPDATE articles SET
                            content_hash=%s, version=version+1,
                            title=%s, subtitle=%s, text_content=%s, text_raw=%s,
                            word_count=%s, author=%s, published_at=%s, updated_at=%s,
                            category=%s, tags=%s, image_url=%s, image_caption=%s,
                            comment_count=%s, scraped_at=NOW(), schema_data=%s
                        WHERE id=%s
                        """,
                        (
                            article.content_hash,
                            article.title, article.subtitle, article.text, article.text_raw,
                            len(article.text) if article.text else 0,
                            article.author, article.published_at, article.updated_at,
                            article.category, tags,
                            article.image_url, article.image_caption, article.comment_count,
                            schema_data, existing_id,
                        ),
                    )
                conn.commit()
                return False

    except psycopg2.Error as e:
        logger.error("DB greška pri upisu %s: %s", article.url, e)
        return False


def get_stats(hours: int = 24) -> List[dict]:
    since = datetime.utcnow() - timedelta(hours=hours)
    try:
        with _connect() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    """
                    SELECT source_id, COUNT(*) as count FROM articles
                    WHERE scraped_at >= %s GROUP BY source_id ORDER BY count DESC
                    """,
                    (since,),
                )
                return [dict(r) for r in cur.fetchall()]
    except psycopg2.Error:
        return []


def get_total() -> int:
    try:
        with _connect() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) FROM articles")
                return cur.fetchone()[0]
    except psycopg2.Error:
        return 0


def get_recent(source_id: Optional[str] = None, hours: int = 24, limit: int = 10) -> List[dict]:
    since = datetime.utcnow() - timedelta(hours=hours)
    try:
        with _connect() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                if source_id:
                    cur.execute(
                        "SELECT url, source_id, title, published_at, category FROM articles "
                        "WHERE source_id=%s AND scraped_at>=%s ORDER BY published_at DESC LIMIT %s",
                        (source_id, since, limit),
                    )
                else:
                    cur.execute(
                        "SELECT url, source_id, title, published_at, category FROM articles "
                        "WHERE scraped_at>=%s ORDER BY published_at DESC LIMIT %s",
                        (since, limit),
                    )
                return [dict(r) for r in cur.fetchall()]
    except psycopg2.Error:
        return []
