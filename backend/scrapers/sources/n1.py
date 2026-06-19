"""N1 Info scraper — RSS-only (listing is JS-rendered, Cloudflare on article pages)."""
from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Optional

import feedparser
from bs4 import BeautifulSoup

from ..base import ArticleData, BaseScraper, ScraperError
from ..utils import clean_text, extract_schema_org, unique_urls

RSS_URL = "https://n1info.rs/feed/"


class N1Scraper(BaseScraper):
    SOURCE_ID = "n1"

    # Cloudflare is present on n1info.rs — article HTML may be blocked.
    # Strategy: use RSS full content as the primary text source;
    # attempt article fetch only for schema.org metadata.

    def __init__(self):
        super().__init__()
        self._rss_cache: Dict[str, feedparser.FeedParserDict] = {}

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

        # Use cached RSS entry; reload if missing
        if url not in self._rss_cache:
            self._load_rss()
        entry = self._rss_cache.get(url)
        if not entry:
            self.logger.warning("Entry not found in RSS for: %s", url)
            return None

        title = entry.get("title", "").strip()

        # RSS provides summary only — fetch full article HTML for complete text
        content_list = entry.get("content", [])
        rss_text_raw = content_list[0].get("value", "") if content_list else entry.get("summary", "")
        soup_rss = BeautifulSoup(rss_text_raw, "lxml")
        rss_text = clean_text(soup_rss.body or soup_rss)

        published_at: Optional[datetime] = None
        if hasattr(entry, "published_parsed") and entry.published_parsed:
            try:
                published_at = datetime(*entry.published_parsed[:6])
            except Exception:
                pass

        tags = [t.term for t in entry.get("tags", []) if hasattr(t, "term")]

        # Fetch article page for full text, author and image (may be Cloudflare-blocked)
        author: Optional[str] = None
        image_url: Optional[str] = None
        schema_data: Optional[dict] = None
        text = rss_text          # fallback to RSS content if HTML fetch fails
        text_raw = rss_text_raw
        try:
            article_resp = self.fetch(url)
            article_soup = BeautifulSoup(article_resp.content, "lxml")
            schema_data = extract_schema_org(article_soup)
            # Use HTML article element for full text
            article_el = article_soup.find("article")
            if article_el:
                html_text = clean_text(article_el)
                if html_text and len(html_text.split()) > len(rss_text.split()):
                    text = html_text
                    text_raw = str(article_el)
            if schema_data:
                a = schema_data.get("author")
                if isinstance(a, dict):
                    author = a.get("name")
                elif isinstance(a, list) and a:
                    author = a[0].get("name") if isinstance(a[0], dict) else str(a[0])
                img = schema_data.get("image")
                if isinstance(img, dict):
                    image_url = img.get("url")
                elif isinstance(img, str):
                    image_url = img
        except ScraperError as exc:
            self.logger.warning("Article page unavailable (Cloudflare?): %s — %s", url, exc)

        if not title or not text:
            self.logger.warning("Empty title or text for: %s", url)
            return None

        return ArticleData(
            url=url,
            source_id=self.SOURCE_ID,
            title=title,
            subtitle=None,
            text=text,
            text_raw=text_raw,  # set to HTML article or RSS fallback
            author=author,
            published_at=published_at,
            updated_at=None,
            category=tags[0] if tags else None,
            tags=tags[1:] if tags else [],
            image_url=image_url,
            image_caption=None,
            comment_count=None,
            content_hash=self.content_hash(title, text),
            scraped_at=datetime.utcnow(),
            schema_data=schema_data,
        )
