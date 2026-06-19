"""Vreme.rs scraper — RSS-only, weekly publication.

NOTE: vreme.rs redirects to vreme.com — use vreme.com directly.
RSS has full article content (12 entries — weekly paper, not daily).
Cloudflare + JS on article pages — use RSS content exclusively.
"""
from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Optional

import feedparser
from bs4 import BeautifulSoup

from ..base import ArticleData, BaseScraper, ScraperError
from ..utils import clean_text, unique_urls

RSS_URL = "https://www.vreme.com/feed/"
FALLBACK_RSS = "https://www.vreme.rs/feed/"


class VremeScraper(BaseScraper):
    SOURCE_ID = "vreme"

    # Weekly newspaper — expect ~12 articles per RSS fetch, not daily volume.
    # Article HTML may be behind Cloudflare/JS — RSS content is authoritative.

    def __init__(self):
        super().__init__()
        self._rss_cache: Dict[str, object] = {}

    def _load_rss(self) -> list:
        for rss_url in [RSS_URL, FALLBACK_RSS]:
            try:
                self.logger.info("Fetching RSS: %s", rss_url)
                resp = self.fetch(rss_url)
                feed = feedparser.parse(resp.text)
                entries = feed.entries or []
                if entries:
                    self.logger.info("RSS returned %d entries (weekly)", len(entries))
                    for entry in entries:
                        if hasattr(entry, "link"):
                            self._rss_cache[entry.link] = entry
                    return entries
            except ScraperError as exc:
                self.logger.warning("RSS fetch failed (%s): %s", rss_url, exc)
        self.logger.error("All RSS URLs failed for vreme")
        return []

    def get_article_urls(self) -> List[str]:
        entries = self._load_rss()
        urls = [e.link for e in entries if hasattr(e, "link")]
        self.logger.info("Vreme: %d articles this week", len(urls))
        return unique_urls(urls)

    def parse_article(self, url: str) -> Optional[ArticleData]:
        self.logger.info("Parsing: %s", url)

        if url not in self._rss_cache:
            self._load_rss()
        entry = self._rss_cache.get(url)
        if not entry:
            self.logger.warning("Entry not in RSS cache: %s", url)
            return None

        title = entry.get("title", "").strip()

        content_list = entry.get("content", [])
        text_raw = content_list[0].get("value", "") if content_list else entry.get("summary", "")
        soup_c = BeautifulSoup(text_raw, "lxml")
        text = clean_text(soup_c.body or soup_c)

        published_at: Optional[datetime] = None
        if hasattr(entry, "published_parsed") and entry.published_parsed:
            try:
                published_at = datetime(*entry.published_parsed[:6])
            except Exception:
                pass

        author: Optional[str] = None
        if hasattr(entry, "author"):
            author = entry.author.strip() if entry.author else None

        tags = [t.term for t in entry.get("tags", []) if hasattr(t, "term")]

        image_url: Optional[str] = None
        # Try enclosure
        for enc in entry.get("enclosures", []):
            if enc.get("type", "").startswith("image"):
                image_url = enc.get("url")
                break
        # Try media thumbnail
        if not image_url:
            media_thumb = entry.get("media_thumbnail", [])
            if media_thumb:
                image_url = media_thumb[0].get("url")

        if not title or not text:
            self.logger.warning("Empty title or text: %s", url)
            return None

        return ArticleData(
            url=url,
            source_id=self.SOURCE_ID,
            title=title,
            subtitle=None,
            text=text,
            text_raw=text_raw,
            author=author,
            published_at=published_at,
            updated_at=None,
            category=tags[0] if tags else None,
            tags=tags[1:] if len(tags) > 1 else [],
            image_url=image_url,
            image_caption=None,
            comment_count=None,
            content_hash=self.content_hash(title, text),
            scraped_at=datetime.utcnow(),
            schema_data=None,
        )
