"""B92.net scraper — multi-feed RSS + HTML article parsing.

RSS feeds cover news, life, and sport categories (~140 unique articles per run).
Article HTML is fetched for full content (RSS has summary only).
URL pattern: /info/KATEGORIJA/BROJ/SLUG/vest or /zivot/KATEGORIJA/BROJ/SLUG/vest
             /sport/KATEGORIJA/BROJ/SLUG/vest
"""
from __future__ import annotations

import re
from datetime import datetime
from typing import Dict, List, Optional

import feedparser
from bs4 import BeautifulSoup

from ..base import ArticleData, BaseScraper, ScraperError
from ..utils import clean_text, parse_sr_date, unique_urls

BASE_URL = "https://www.b92.net"

RSS_FEEDS = [
    "https://www.b92.net/rss/latest",
    "https://www.b92.net/rss/b92/info",
    "https://www.b92.net/rss/b92/info/politika",
    "https://www.b92.net/rss/b92/info/drustvo",
    "https://www.b92.net/rss/b92/info/hronika",
    "https://www.b92.net/rss/b92/zivot",
    "https://www.b92.net/rss/sport",
    "https://www.b92.net/rss/sport/fudbal",
    "https://www.b92.net/rss/sport/kosarka",
]


class B92Scraper(BaseScraper):
    SOURCE_ID = "b92"

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
        self.logger.info("Total unique RSS entries: %d", len(self._rss_cache))

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

        # Title
        title_el = soup.find("h1", class_=lambda c: c and "section-title" in c.lower())
        if not title_el:
            title_el = soup.find("h1")
        title = title_el.get_text(strip=True) if title_el else ""
        if not title:
            og = soup.find("meta", property="og:title")
            title = og["content"].strip() if og and og.get("content") else ""
        if not title:
            entry = self._rss_cache.get(url)
            if entry:
                title = entry.get("title", "")
        if not title:
            self.logger.warning("No title: %s", url)
            return None

        # Subtitle
        subtitle: Optional[str] = None
        lead_el = soup.find(class_=lambda c: c and "lead" in c.lower())
        if lead_el:
            candidate = lead_el.get_text(strip=True)
            if len(candidate) > 20 and "b92" not in candidate.lower():
                subtitle = candidate
        if not subtitle:
            og_desc = soup.find("meta", property="og:description")
            if og_desc and og_desc.get("content") and len(og_desc["content"]) > 20:
                subtitle = og_desc["content"].strip()

        # Text — use section.single-news to avoid sidebar (~1700w with main)
        content_el = soup.select_one("section.single-news") or soup.find("main")
        if content_el:
            # Remove related-news and category-box sidebars embedded in the section
            for rm in content_el.find_all("section", class_=lambda c: c and any(
                x in " ".join(c if isinstance(c, list) else [c]).lower()
                for x in ["related", "category-box", "similar"]
            )):
                rm.decompose()
        text_raw = str(content_el) if content_el else ""
        text = clean_text(content_el) if content_el else ""

        # Author
        author: Optional[str] = None
        author_el = soup.find(class_=lambda c: c and "author" in c.lower())
        if author_el:
            raw = author_el.get_text(strip=True)
            author = re.sub(r"^(Izvor|Autor|By)\s*:?\s*", "", raw, flags=re.IGNORECASE).strip() or None

        # Timestamp — prefer RSS pub date
        published_at: Optional[datetime] = None
        entry = self._rss_cache.get(url)
        if entry and hasattr(entry, "published_parsed") and entry.published_parsed:
            try:
                published_at = datetime(*entry.published_parsed[:6])
            except Exception:
                pass
        if not published_at:
            date_el = soup.find(class_=lambda c: c and "date" in c.lower())
            if date_el:
                published_at = parse_sr_date(date_el.get_text(strip=True), default_year=datetime.utcnow().year)
        if not published_at:
            og_time = soup.find("meta", property="article:published_time")
            if og_time and og_time.get("content"):
                published_at = parse_sr_date(og_time["content"])

        # Category from URL
        category: Optional[str] = None
        m = re.search(r"/(?:info|zivot)/([^/]+)/\d+/", url)
        if m:
            category = m.group(1).replace("-", " ").title()
        # Fall back to RSS tag
        if not category and entry:
            tags_rss = entry.get("tags", [])
            if tags_rss:
                category = tags_rss[0].get("term", "")

        # Image
        image_url: Optional[str] = None
        og_img = soup.find("meta", property="og:image")
        if og_img and og_img.get("content"):
            image_url = og_img["content"]
        if not image_url:
            article_el = soup.find("article")
            if article_el:
                img = article_el.find("img")
                if img:
                    image_url = img.get("src") or img.get("data-src")
        if image_url and image_url.startswith("/"):
            image_url = BASE_URL + image_url

        return ArticleData(
            url=url,
            source_id=self.SOURCE_ID,
            title=title,
            subtitle=subtitle,
            text=text,
            text_raw=text_raw,
            author=author,
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
