"""Srbija Danas (sd.rs) scraper — RSS-based (100 entries at /rss.xml).

Despite initial reports of Cloudflare blocking, /rss.xml returns 100 entries.
HTML listing is JS-rendered/Cloudflare-blocked; RSS is the reliable source.
"""
from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Optional

import feedparser
from bs4 import BeautifulSoup

from ..base import ArticleData, BaseScraper, ScraperError
from ..utils import clean_text, parse_sr_date, unique_urls

RSS_URL = "https://www.sd.rs/rss.xml"


class SrbijaDanasScraper(BaseScraper):
    SOURCE_ID = "sd"

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
        if not entry:
            self.logger.warning("Entry not in RSS cache: %s", url)
            return None

        title = entry.get("title", "").strip()
        content_list = entry.get("content", [])
        rss_raw = content_list[0].get("value", "") if content_list else entry.get("summary", "")
        soup_rss = BeautifulSoup(rss_raw, "lxml")
        rss_text = clean_text(soup_rss.body or soup_rss)
        text = rss_text
        text_raw = rss_raw

        published_at: Optional[datetime] = None
        if hasattr(entry, "published_parsed") and entry.published_parsed:
            try:
                published_at = datetime(*entry.published_parsed[:6])
            except Exception:
                pass

        updated_at: Optional[datetime] = None
        if hasattr(entry, "updated_parsed") and entry.updated_parsed:
            try:
                updated_at = datetime(*entry.updated_parsed[:6])
            except Exception:
                pass

        author: Optional[str] = None
        if hasattr(entry, "author") and entry.author:
            author = entry.author.strip()

        tags = [t.term for t in entry.get("tags", []) if hasattr(t, "term")]
        category = tags.pop(0) if tags else None

        image_url: Optional[str] = None
        for enc in entry.get("enclosures", []):
            if enc.get("type", "").startswith("image"):
                image_url = enc.get("url")
                break
        if not image_url:
            media_thumb = entry.get("media_thumbnail", [])
            if media_thumb:
                image_url = media_thumb[0].get("url")

        # Fetch full article HTML for complete text (RSS provides summary only ~35w)
        try:
            html_resp = self.fetch(url)
            html_soup = BeautifulSoup(html_resp.content, "lxml")
            article_el = html_soup.find("article")
            if article_el:
                html_text = clean_text(article_el)
                if html_text and len(html_text.split()) > len(rss_text.split()):
                    text = html_text
                    text_raw = str(article_el)
            if not image_url:
                og_img = html_soup.find("meta", property="og:image")
                if og_img and og_img.get("content"):
                    image_url = og_img["content"]
        except ScraperError:
            pass  # keep RSS content as fallback

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
            updated_at=updated_at,
            category=category,
            tags=tags,
            image_url=image_url,
            image_caption=None,
            comment_count=None,
            content_hash=self.content_hash(title, text),
            scraped_at=datetime.utcnow(),
            schema_data=None,
        )
