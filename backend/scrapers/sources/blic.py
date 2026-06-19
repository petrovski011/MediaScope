"""Blic.rs scraper — multi-feed RSS + HTML article parsing.

RSS at /rss/danasnje-vesti and 9 category feeds give ~400 unique articles.
Article HTML is fetched for full content (RSS content field is image-only).
Ring Publishing CMS: article URLs follow /KATEGORIJA/SLUG/SHORTID pattern.
"""
from __future__ import annotations

import re
from datetime import datetime
from typing import Dict, List, Optional

import feedparser
from bs4 import BeautifulSoup

from ..base import ArticleData, BaseScraper, ScraperError
from ..utils import clean_text, extract_schema_org, parse_sr_date, unique_urls

BASE_URL = "https://www.blic.rs"

RSS_FEEDS = [
    "https://www.blic.rs/rss/danasnje-vesti",
    "https://www.blic.rs/rss/Vesti",
    "https://www.blic.rs/rss/Vesti/Politika",
    "https://www.blic.rs/rss/Vesti/Hronika",
    "https://www.blic.rs/rss/Svet",
    "https://www.blic.rs/rss/Sport",
    "https://www.blic.rs/rss/Zabava",
    "https://www.blic.rs/rss/Zabava/Kultura",
    "https://www.blic.rs/rss/Zabava/Zdravlje",
    "https://www.blic.rs/rss/Ekonomija",
]


class BlicScraper(BaseScraper):
    SOURCE_ID = "blic"

    def __init__(self):
        super().__init__()
        self._rss_cache: Dict[str, object] = {}

    def _load_rss(self) -> list:
        all_entries: list = []
        for rss_url in RSS_FEEDS:
            self.logger.info("Fetching RSS: %s", rss_url)
            try:
                resp = self.fetch(rss_url)
                feed = feedparser.parse(resp.content)
                entries = feed.entries or []
                self.logger.debug("  %d entries from %s", len(entries), rss_url)
                for entry in entries:
                    if hasattr(entry, "link") and entry.link not in self._rss_cache:
                        self._rss_cache[entry.link] = entry
                        all_entries.append(entry)
            except ScraperError as exc:
                self.logger.warning("RSS fetch failed (%s): %s", rss_url, exc)
        self.logger.info("Total unique RSS entries: %d", len(self._rss_cache))
        return all_entries

    def get_article_urls(self) -> List[str]:
        self._load_rss()
        return unique_urls(list(self._rss_cache.keys()))

    def parse_article(self, url: str) -> Optional[ArticleData]:
        self.logger.info("Parsing: %s", url)
        try:
            resp = self.fetch(url)
        except ScraperError as exc:
            self.logger.error("Fetch failed: %s — %s", url, exc)
            return None

        soup = BeautifulSoup(resp.content, "lxml")
        schema_data = extract_schema_org(soup)

        # Title
        h1 = soup.find("h1")
        title = h1.get_text(strip=True) if h1 else ""
        if not title and schema_data:
            title = schema_data.get("headline", "")
        if not title:
            og = soup.find("meta", property="og:title")
            title = og["content"].strip() if og and og.get("content") else ""
        # Fall back to RSS title
        if not title:
            entry = self._rss_cache.get(url)
            if entry:
                title = entry.get("title", "")
        if not title:
            self.logger.warning("No title: %s", url)
            return None

        # Subtitle
        subtitle: Optional[str] = None
        og_desc = soup.find("meta", property="og:description")
        if og_desc and og_desc.get("content") and len(og_desc["content"]) > 20:
            subtitle = og_desc["content"].strip()
        if not subtitle and schema_data:
            subtitle = schema_data.get("description") or None

        # Text
        text_el = (
            soup.find(class_=lambda c: c and "article-text" in c.lower())
            or soup.find(class_=lambda c: c and "article__body" in c.lower())
            or soup.find("article")
            or soup.find("main")
        )
        text_raw = str(text_el) if text_el else ""
        text = clean_text(text_el) if text_el else ""

        # Author — Blic appends job title/bio directly after the name with no separator,
        # e.g. "Dušan LukićNovinarstvom se bavi..." or "Branko JanačkovićŠef dopisništva".
        # Split on the first lowercase→uppercase boundary to extract only the name.
        author: Optional[str] = None
        author_el = soup.find(class_=lambda c: c and "author" in c.lower())
        if author_el:
            raw = author_el.get_text(strip=True)
            if raw:
                name = re.split(r"(?<=[a-zčćžšđ])(?=[A-ZČĆŽŠĐ])", raw)[0].strip()
                author = name if name else None
        if not author and schema_data:
            a_field = schema_data.get("author")
            if isinstance(a_field, dict):
                author = a_field.get("name")

        # Timestamp — prefer RSS pub date (accurate), fall back to HTML
        published_at: Optional[datetime] = None
        entry = self._rss_cache.get(url)
        if entry and hasattr(entry, "published_parsed") and entry.published_parsed:
            try:
                published_at = datetime(*entry.published_parsed[:6])
            except Exception:
                pass
        if not published_at and schema_data:
            published_at = parse_sr_date(schema_data.get("datePublished", ""))
        if not published_at:
            time_el = soup.find("time", attrs={"datetime": True})
            if time_el:
                published_at = parse_sr_date(time_el["datetime"])

        updated_at: Optional[datetime] = None
        if schema_data:
            updated_at = parse_sr_date(schema_data.get("dateModified", ""))

        # Category from URL: /KATEGORIJA/slug/id
        category: Optional[str] = None
        m = re.search(r"blic\.rs/([a-z]+)/", url)
        if m:
            category = m.group(1).title()

        # Tags
        tags = [
            a.get_text(strip=True)
            for a in soup.find_all("a", href=lambda h: h and "/tag" in h)
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
            subtitle=subtitle,
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
