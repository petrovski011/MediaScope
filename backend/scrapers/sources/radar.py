"""Radar scraper — RSS-based (radar.nova.rs).

radar.rs redirects to radar.nova.rs — use radar.nova.rs directly.
WP REST API requires authentication (401) — use RSS feed (50 entries).
Paywall detection: log warning for short content with paywall signals.
og:published_time and og:updated_time in ISO8601 format.
"""
from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Optional

import feedparser
from bs4 import BeautifulSoup

from ..base import ArticleData, BaseScraper, ScraperError
from ..utils import clean_text, extract_schema_org, parse_sr_date, unique_urls

RSS_URL = "https://radar.nova.rs/feed/"
BASE_URL = "https://radar.nova.rs"

_PAYWALL_SIGNALS = frozenset(["pretplata", "paywall", "premium", "subscriber"])


def _detect_paywall(text: str) -> bool:
    return any(signal in text.lower() for signal in _PAYWALL_SIGNALS)


class RadarScraper(BaseScraper):
    SOURCE_ID = "radar"

    # NOTE: radar.rs → redirects to radar.nova.rs
    # WP REST API returns 401 (requires auth) — RSS with 50 entries used instead.

    def __init__(self):
        super().__init__()
        self._rss_cache: Dict[str, object] = {}

    def _load_rss(self) -> list:
        self.logger.info("Fetching RSS: %s", RSS_URL)
        try:
            resp = self.fetch(RSS_URL)
            feed = feedparser.parse(resp.text)
            entries = feed.entries or []
            self.logger.info("RSS returned %d entries", len(entries))
            for entry in entries:
                if hasattr(entry, "link"):
                    self._rss_cache[entry.link] = entry
            return entries
        except ScraperError as exc:
            self.logger.error("RSS fetch failed: %s", exc)
            return []

    def get_article_urls(self) -> List[str]:
        entries = self._load_rss()
        urls = [e.link for e in entries if hasattr(e, "link")]
        return unique_urls(urls)

    def parse_article(self, url: str) -> Optional[ArticleData]:
        self.logger.info("Parsing: %s", url)
        # Fetch article page for full content (RSS may have truncated excerpts)
        try:
            resp = self.fetch(url)
        except ScraperError as exc:
            self.logger.error("Fetch failed: %s — %s", url, exc)
            # Fallback to RSS content
            return self._parse_from_rss(url)

        soup = BeautifulSoup(resp.content, "lxml")
        schema_data = extract_schema_org(soup)

        # Title
        og_title = soup.find("meta", property="og:title")
        title = og_title["content"].strip() if og_title and og_title.get("content") else ""
        if not title:
            h1 = soup.find("h1")
            title = h1.get_text(strip=True) if h1 else ""

        if not title:
            return self._parse_from_rss(url)

        # Content
        main_el = soup.find("main") or soup.find("article") or soup.find(class_="entry-content")
        text = clean_text(main_el) if main_el else ""
        text_raw = str(main_el) if main_el else ""

        # Paywall detection
        if _detect_paywall(text) and len(text.split()) < 50:
            self.logger.warning("[radar] Paywall suspected for: %s", url)

        # Timestamps — og:published_time / og:updated_time confirmed ISO8601
        published_at: Optional[datetime] = None
        og_pub = soup.find("meta", property="og:published_time") or soup.find(
            "meta", property="article:published_time"
        )
        if og_pub and og_pub.get("content"):
            published_at = parse_sr_date(og_pub["content"])
        if not published_at and schema_data:
            published_at = parse_sr_date(schema_data.get("datePublished", ""))

        updated_at: Optional[datetime] = None
        og_mod = soup.find("meta", property="og:updated_time") or soup.find(
            "meta", property="article:modified_time"
        )
        if og_mod and og_mod.get("content"):
            updated_at = parse_sr_date(og_mod["content"])

        # Author
        author: Optional[str] = None
        if schema_data:
            a = schema_data.get("author")
            if isinstance(a, dict):
                author = a.get("name")
        if not author:
            author_el = soup.find(class_=lambda c: c and "author" in c.lower())
            if author_el:
                author = author_el.get_text(strip=True)

        # Category / tags
        category: Optional[str] = None
        tags: list[str] = []
        cat_el = soup.find(class_=lambda c: c and "categor" in c.lower())
        if cat_el:
            category = cat_el.get_text(strip=True)
        tags = [
            a.get_text(strip=True)
            for a in soup.find_all("a", href=lambda h: h and "/tag/" in h)
            if a.get_text(strip=True)
        ]

        # Image
        image_url: Optional[str] = None
        og_img = soup.find("meta", property="og:image")
        if og_img and og_img.get("content"):
            image_url = og_img["content"]

        return ArticleData(
            url=url,
            source_id=self.SOURCE_ID,
            title=title,
            subtitle=None,
            text=text,
            text_raw=text_raw,
            author=author,
            published_at=published_at,
            updated_at=updated_at,
            category=category,
            tags=tags,
            image_url=image_url,
            image_caption=None,
            comment_count=None,
            content_hash=self.content_hash(title, text),
            scraped_at=datetime.utcnow(),
            schema_data=schema_data,
        )

    def _parse_from_rss(self, url: str) -> Optional[ArticleData]:
        """Fallback: parse from cached RSS entry."""
        if url not in self._rss_cache:
            self._load_rss()
        entry = self._rss_cache.get(url)
        if not entry:
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

        if not title:
            return None

        return ArticleData(
            url=url,
            source_id=self.SOURCE_ID,
            title=title,
            subtitle=None,
            text=text,
            text_raw=text_raw,
            author=None,
            published_at=published_at,
            updated_at=None,
            category=None,
            tags=[],
            image_url=None,
            image_caption=None,
            comment_count=None,
            content_hash=self.content_hash(title, text),
            scraped_at=datetime.utcnow(),
            schema_data=None,
        )
