"""BIRN (Balkan Investigative Reporting Network) scraper — RSS-based.

Feed at birn.eu.com/feed/ (30 entries) — investigative journalism, high-value source.
birn.rs/feed/ returns 0 entries; balkaninsight.com/feed/ (90 entries) is English only.
"""
from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Optional

import feedparser
from bs4 import BeautifulSoup

from ..base import ArticleData, BaseScraper, ScraperError
from ..utils import clean_text, parse_sr_date, unique_urls

RSS_URL = "https://birn.eu.com/feed/"
FALLBACK_RSS = "https://balkaninsight.com/feed/"


class BirnScraper(BaseScraper):
    SOURCE_ID = "birn"

    def __init__(self):
        super().__init__()
        self._rss_cache: Dict[str, object] = {}
        self._feed_url_used: str = RSS_URL

    def _load_rss(self) -> list:
        for rss_url in [RSS_URL, FALLBACK_RSS]:
            self.logger.info("Fetching RSS: %s", rss_url)
            try:
                resp = self.fetch(rss_url)
                feed = feedparser.parse(resp.content)
                entries = feed.entries or []
                if entries:
                    self._feed_url_used = rss_url
                    self.logger.info("RSS returned %d entries from %s", len(entries), rss_url)
                    for entry in entries:
                        if hasattr(entry, "link"):
                            self._rss_cache[entry.link] = entry
                    return entries
            except ScraperError as exc:
                self.logger.warning("RSS fetch failed (%s): %s", rss_url, exc)
        self.logger.error("All RSS URLs failed for birn")
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
        if not image_url:
            img_el = soup_c.find("img")
            if img_el:
                image_url = img_el.get("src") or img_el.get("data-src")

        if not title:
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
            category=category,
            tags=tags,
            image_url=image_url,
            image_caption=None,
            comment_count=None,
            content_hash=self.content_hash(title, text),
            scraped_at=datetime.utcnow(),
            schema_data=None,
        )
