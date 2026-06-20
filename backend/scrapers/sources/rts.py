"""RTS (rts.rs) scraper — RSS listing + HTML article parsing.

URL discovery via RSS (reliable, avoids IP-based HTML blocking).
Full text extracted from article pages.
RSS also provides exact timestamps and Cyrillic subtitle, used as fallback.
"""
from __future__ import annotations

import re
from calendar import timegm
from datetime import datetime
from typing import Dict, List, Optional

import feedparser
from bs4 import BeautifulSoup

from ..base import ArticleData, BaseScraper, ScraperError
from ..utils import clean_text, cyrillic_to_latin, unique_urls

RSS_URL = "https://www.rts.rs/vesti/rss.html"
BASE_URL = "https://www.rts.rs"

# Article URL pattern: /vesti/KATEGORIJA/BROJ/NASLOV.html
_ARTICLE_RE = re.compile(r"/vesti/[^/]+/\d+/[^/]+\.html")


class RtsScraper(BaseScraper):
    SOURCE_ID = "rts"

    def __init__(self):
        super().__init__()
        # Populated by get_article_urls(); consumed by parse_article()
        self._rss_meta: Dict[str, dict] = {}

    def get_article_urls(self) -> List[str]:
        self.logger.info("Fetching RSS: %s", RSS_URL)
        try:
            resp = self.fetch(RSS_URL)
        except ScraperError as exc:
            self.logger.error("RSS fetch failed: %s", exc)
            return []

        feed = feedparser.parse(resp.content)
        urls: list[str] = []
        for entry in feed.entries:
            link = entry.get("link", "")
            if not link or not _ARTICLE_RE.search(link):
                continue
            full = link if link.startswith("http") else BASE_URL + link
            urls.append(full)

            # Cache RSS metadata for use in parse_article()
            published_at: Optional[datetime] = None
            if entry.get("published_parsed"):
                published_at = datetime(*entry.published_parsed[:6])

            summary = entry.get("summary", "") or ""
            category = None
            if entry.get("tags"):
                category = entry["tags"][0].get("term", "")

            self._rss_meta[full] = {
                "title": cyrillic_to_latin(entry.get("title", "")),
                "subtitle": cyrillic_to_latin(summary) if summary else None,
                "published_at": published_at,
                "category": cyrillic_to_latin(category) if category else None,
            }

        result = unique_urls(urls)
        self.logger.info("Found %d article URLs via RSS", len(result))
        return result

    def parse_article(self, url: str) -> Optional[ArticleData]:
        self.logger.info("Parsing: %s", url)
        rss = self._rss_meta.get(url, {})

        try:
            resp = self.fetch(url)
        except ScraperError as exc:
            self.logger.error("Fetch failed: %s — %s", url, exc)
            return None

        soup = BeautifulSoup(resp.content, "lxml")

        # Title — OG tag first, then h1, fallback to RSS
        og_title = soup.find("meta", property="og:title")
        title_raw = ""
        if og_title and og_title.get("content"):
            title_raw = og_title["content"].strip()
        if not title_raw:
            h1 = soup.find("h1")
            title_raw = h1.get_text(strip=True) if h1 else ""
        title = cyrillic_to_latin(title_raw) or rss.get("title", "")

        if not title:
            self.logger.warning("No title: %s", url)
            return None

        # Subtitle / lead — HTML first, RSS summary as fallback
        subtitle: Optional[str] = None
        lead_el = soup.find(class_=lambda c: c and "lead" in c.lower())
        if lead_el:
            subtitle = cyrillic_to_latin(lead_el.get_text(strip=True))
        if not subtitle:
            subtitle = rss.get("subtitle")

        # Text — two RTS layouts:
        # 1. Short-story: div.short-story-body (skip empty placeholder)
        # 2. Full story: div.story-wrapper → biggest direct-child div
        content_el = None
        for candidate in soup.find_all("div", class_="short-story-body"):
            if len(candidate.get_text().split()) > 10:
                content_el = candidate
                break
        if not content_el:
            wrapper = soup.find("div", class_="story-wrapper")
            if wrapper:
                children = [d for d in wrapper.find_all("div", recursive=False)
                            if len(d.get_text().split()) > 50]
                if children:
                    content_el = max(children, key=lambda d: len(d.get_text()))
        if not content_el:
            content_el = soup.find("article") or soup.find("main")
        text_raw = str(content_el) if content_el else ""
        text = cyrillic_to_latin(clean_text(content_el)) if content_el else ""

        # Published timestamp — RSS is most reliable (article page uses custom format)
        published_at: Optional[datetime] = rss.get("published_at")

        # Category — HTML first, RSS fallback
        category: Optional[str] = None
        section_el = soup.find(class_=lambda c: c and "section" in c.lower())
        if section_el:
            category = cyrillic_to_latin(section_el.get_text(strip=True))
        if not category:
            m = re.search(r"/vesti/([^/]+)/", url)
            if m:
                category = m.group(1).replace("-", " ").title()
        if not category:
            category = rss.get("category")

        # Image
        image_url: Optional[str] = None
        og_img = soup.find("meta", property="og:image")
        if og_img and og_img.get("content"):
            image_url = og_img["content"]
        if not image_url:
            article_el = soup.find("article")
            if article_el:
                img_el = article_el.find("img")
                if img_el:
                    image_url = img_el.get("src") or img_el.get("data-src")

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
