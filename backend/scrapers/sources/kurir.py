"""Kurir.rs scraper — RSS-based (100 entries).

Despite initial reports of malformed XML, the /rss endpoint parses correctly.
Site uses Nuxt.js so HTML listing is JS-rendered, but RSS works fine.
"""
from __future__ import annotations

import re
from datetime import datetime
from typing import Dict, List, Optional

import feedparser
from bs4 import BeautifulSoup

from ..base import ArticleData, BaseScraper, ScraperError
from ..utils import clean_text, extract_schema_org, parse_sr_date, unique_urls

RSS_URL = "https://www.kurir.rs/rss"


class KurirScraper(BaseScraper):
    SOURCE_ID = "kurir"

    # Nuxt.js site — HTML listing is JS-rendered (0 links via BeautifulSoup).
    # RSS at /rss provides 100 entries and works correctly.

    def __init__(self):
        super().__init__()
        self._rss_cache: Dict[str, object] = {}

    def _load_rss(self) -> list:
        self.logger.info("Fetching RSS: %s", RSS_URL)
        try:
            resp = self.fetch(RSS_URL)
            feed = feedparser.parse(resp.content)
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

        if url not in self._rss_cache:
            self._load_rss()
        entry = self._rss_cache.get(url)

        # Try to fetch article page for full content
        try:
            resp = self.fetch(url)
            soup = BeautifulSoup(resp.content, "lxml")
            schema_data = extract_schema_org(soup)

            h1 = soup.find("h1")
            title = h1.get_text(strip=True) if h1 else ""
            if not title and schema_data:
                title = schema_data.get("headline", "")
            if not title and entry:
                title = entry.get("title", "").strip()

            # Content: article body
            content_el = (
                soup.find(class_=lambda c: c and "article-body" in c.lower())
                or soup.find(class_=lambda c: c and "article__content" in c.lower())
                or soup.find("article")
                or soup.find("main")
            )
            text_raw = str(content_el) if content_el else ""
            text = clean_text(content_el) if content_el else ""

            # Author
            author: Optional[str] = None
            author_el = soup.find(class_=lambda c: c and "author" in c.lower())
            if author_el:
                author = author_el.get_text(strip=True)
            if not author and schema_data:
                a = schema_data.get("author")
                if isinstance(a, dict):
                    author = a.get("name")

            # Timestamp — prefer schema.org
            published_at: Optional[datetime] = None
            if schema_data:
                published_at = parse_sr_date(schema_data.get("datePublished", ""))
            if not published_at:
                time_el = soup.find("time", attrs={"datetime": True})
                if time_el:
                    published_at = parse_sr_date(time_el["datetime"])
            if not published_at and entry and hasattr(entry, "published_parsed") and entry.published_parsed:
                try:
                    published_at = datetime(*entry.published_parsed[:6])
                except Exception:
                    pass

            updated_at: Optional[datetime] = None
            if schema_data:
                updated_at = parse_sr_date(schema_data.get("dateModified", ""))

            # Category / tags
            category: Optional[str] = None
            if schema_data:
                category = schema_data.get("articleSection", "")
            # Fallback: extract from URL — kurir.rs/KATEGORIJA/[subcat/]BROJ/slug
            if not category:
                m = re.match(r"https?://[^/]+/([a-z][a-z-]+)/", url)
                if m:
                    category = m.group(1).replace("-", " ").title()
            tags = [
                a.get_text(strip=True)
                for a in soup.find_all("a", href=lambda h: h and "/tag" in h)
                if a.get_text(strip=True)
            ]

            # Image
            image_url: Optional[str] = None
            if schema_data:
                img = schema_data.get("image")
                if isinstance(img, dict):
                    image_url = img.get("url")
                elif isinstance(img, str):
                    image_url = img
            if not image_url:
                og_img = soup.find("meta", property="og:image")
                if og_img and og_img.get("content"):
                    image_url = og_img["content"]

            if not title or not text:
                return self._parse_from_rss_entry(url, entry)

            return ArticleData(
                url=url,
                source_id=self.SOURCE_ID,
                title=title,
                subtitle=schema_data.get("description") if schema_data else None,
                text=text,
                text_raw=text_raw,
                author=author,
                published_at=published_at,
                updated_at=updated_at,
                category=category or None,
                tags=tags,
                image_url=image_url,
                image_caption=None,
                comment_count=None,
                content_hash=self.content_hash(title, text),
                scraped_at=datetime.utcnow(),
                schema_data=schema_data,
            )

        except ScraperError as exc:
            self.logger.warning("Article page unavailable: %s — %s", url, exc)
            return self._parse_from_rss_entry(url, entry)

    def _parse_from_rss_entry(self, url: str, entry) -> Optional[ArticleData]:
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
