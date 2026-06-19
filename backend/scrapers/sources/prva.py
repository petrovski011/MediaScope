"""Prva.rs scraper — RSS feeds + HTML listing + article parsing.

RSS at /rss/showbiz/vesti (20) and /rss/info/vesti (20).
HTML listing from /zivot and /najava adds ~30 more.
Total: ~70 unique articles.
Article URL pattern: /SEKCIJA/KATEGORIJA/BROJ/SLUG/vest
"""
from __future__ import annotations

import re
from datetime import datetime
from typing import Dict, List, Optional

import feedparser
from bs4 import BeautifulSoup

from ..base import ArticleData, BaseScraper, ScraperError
from ..utils import clean_text, parse_sr_date, unique_urls

BASE_URL = "https://www.prva.rs"

RSS_FEEDS = [
    "https://www.prva.rs/rss/showbiz/vesti",
    "https://www.prva.rs/rss/info/vesti",
]

HTML_LISTINGS = [
    "https://www.prva.rs/",
    "https://www.prva.rs/zivot",
    "https://www.prva.rs/najava",
]

# Matches /SEKCIJA/KATEGORIJA/BROJ/slug/vest (any nesting depth)
_ARTICLE_RE = re.compile(r"/[a-z-]+/[a-z-]+/\d+/[a-z0-9-]+/vest(?:$|[/?#])")


class PrvaScraper(BaseScraper):
    SOURCE_ID = "prva"

    def __init__(self):
        super().__init__()
        self._rss_cache: Dict[str, object] = {}

    def _load_rss(self) -> None:
        for rss_url in RSS_FEEDS:
            self.logger.info("Fetching RSS: %s", rss_url)
            try:
                resp = self.fetch(rss_url)
                feed = feedparser.parse(resp.content)
                for entry in feed.entries or []:
                    if hasattr(entry, "link") and entry.link not in self._rss_cache:
                        self._rss_cache[entry.link] = entry
            except ScraperError as exc:
                self.logger.warning("RSS fetch failed (%s): %s", rss_url, exc)

    def get_article_urls(self) -> List[str]:
        self._load_rss()
        urls: list[str] = list(self._rss_cache.keys())

        # Supplement with HTML listing pages
        for listing_url in HTML_LISTINGS:
            self.logger.info("Fetching listing: %s", listing_url)
            try:
                resp = self.fetch(listing_url)
                soup = BeautifulSoup(resp.content, "lxml")
                for a in soup.find_all("a", href=True):
                    href = a["href"]
                    if _ARTICLE_RE.search(href):
                        full = href if href.startswith("http") else BASE_URL + href
                        urls.append(full)
            except ScraperError as exc:
                self.logger.warning("Listing fetch failed (%s): %s", listing_url, exc)

        result = unique_urls(urls)
        self.logger.info("Found %d article URLs", len(result))
        return result

    def parse_article(self, url: str) -> Optional[ArticleData]:
        self.logger.info("Parsing: %s", url)
        try:
            resp = self.fetch(url)
        except ScraperError as exc:
            self.logger.error("Fetch failed: %s — %s", url, exc)
            return None

        soup = BeautifulSoup(resp.content, "lxml")

        # Title — OG tag is authoritative
        og_title = soup.find("meta", property="og:title")
        title = og_title["content"].strip() if og_title and og_title.get("content") else ""
        if not title:
            h1 = soup.find("h1")
            title = h1.get_text(strip=True) if h1 else ""
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

        # Text — prva.rs layout: section.single-news > div.container > div.single-news-layout
        # div.single-news-main is the article body; sibling div.single-news-sidebar is noise (892w)
        content_el = (
            soup.select_one("div.single-news-main")
            or soup.find("article")
            or soup.find("main")
        )
        text_raw = str(content_el) if content_el else ""
        text = clean_text(content_el) if content_el else ""

        # Timestamp — prefer OG meta, fall back to RSS pub date
        published_at: Optional[datetime] = None
        og_time = soup.find("meta", property="og:published_time") or soup.find(
            "meta", property="article:published_time"
        )
        if og_time and og_time.get("content"):
            published_at = parse_sr_date(og_time["content"])
        if not published_at:
            entry = self._rss_cache.get(url)
            if entry and hasattr(entry, "published_parsed") and entry.published_parsed:
                try:
                    published_at = datetime(*entry.published_parsed[:6])
                except Exception:
                    pass
        if not published_at:
            time_el = soup.find(class_=lambda c: c and "time" in c.lower())
            if time_el:
                raw = time_el.get_text(strip=True)
                if re.search(r"\d{4}", raw):
                    published_at = parse_sr_date(raw)

        # Category from URL: /SEKCIJA/KATEGORIJA/BROJ/...
        category: Optional[str] = None
        m = re.search(r"/([a-z-]+)/([a-z-]+)/\d+/", url)
        if m:
            category = m.group(2).replace("-", " ").title()

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
            author=None,
            published_at=published_at,
            updated_at=None,
            category=category,
            tags=[],
            image_url=image_url,
            image_caption=None,
            comment_count=None,
            content_hash=self.content_hash(title, text),
            scraped_at=datetime.utcnow(),
            schema_data=None,
        )
