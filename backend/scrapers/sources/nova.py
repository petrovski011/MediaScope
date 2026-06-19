"""Nova.rs scraper — RSS for URLs, HTML for article parsing. Cloudflare present."""
from __future__ import annotations

import re
from datetime import datetime
from typing import Dict, List, Optional

import feedparser
from bs4 import BeautifulSoup

from ..base import ArticleData, BaseScraper, ScraperError
from ..utils import clean_text, extract_schema_org, parse_sr_date, unique_urls

RSS_URL = "https://nova.rs/feed/"
BASE_URL = "https://nova.rs"

# Nova.rs uses Tailwind CSS — class names like "shadow-*", "fade-*" etc. contain
# common substrings ("ad", "social", etc.) and must NOT be used for noise detection.
# Only decompose elements whose classes start with a known noise prefix.
_NOVA_NOISE_PREFIXES = ("related-", "promo-", "newsletter-", "comments-section")
_NOVA_NOISE_EXACT = frozenset(["comments-badge", "social-share", "promo-block"])


class NovaScraper(BaseScraper):
    SOURCE_ID = "nova"

    # Cloudflare is present — some article pages may be blocked.

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

        if not title:
            self.logger.warning("No title: %s", url)
            return None

        # Text in <article> — nova.rs stores paragraphs in div.rich-text-block elements.
        # Do NOT use broad substring class matching (Tailwind utility classes like
        # "shadow-lg", "fade-visible" contain "ad" and would kill content elements).
        article_el = soup.find("article")
        text = ""
        text_raw = str(article_el) if article_el else ""
        if article_el:
            # Primary: collect rich-text-block content divs
            blocks = article_el.find_all("div", class_="rich-text-block")
            if blocks:
                text = "\n\n".join(t for t in (clean_text(b) for b in blocks) if t)
            else:
                # Fallback: remove known noise by exact/prefix class names only
                for rm in article_el.find_all(lambda tag: any(
                    cls in _NOVA_NOISE_EXACT
                    or any(cls.startswith(p) for p in _NOVA_NOISE_PREFIXES)
                    for cls in tag.get("class", [])
                )):
                    rm.decompose()
                text = clean_text(article_el)

        # Author
        author: Optional[str] = None
        author_el = soup.find(class_=lambda c: c and "author" in c.lower())
        if author_el:
            author = author_el.get_text(strip=True)
        if not author and schema_data:
            a = schema_data.get("author")
            if isinstance(a, dict):
                author = a.get("name")
            elif isinstance(a, list) and a:
                author = a[0].get("name") if isinstance(a[0], dict) else str(a[0])

        # Timestamp — "17. jun. 2026. 16:03"
        published_at: Optional[datetime] = None
        time_el = soup.find(class_=lambda c: c and "time" in c.lower())
        if time_el:
            published_at = parse_sr_date(time_el.get_text(strip=True))
        if not published_at and schema_data:
            published_at = parse_sr_date(schema_data.get("datePublished", ""))

        # Updated from OG tag
        updated_at: Optional[datetime] = None
        og_updated = soup.find("meta", property="og:updated_time")
        if og_updated and og_updated.get("content"):
            updated_at = parse_sr_date(og_updated["content"])
        if not updated_at and schema_data:
            updated_at = parse_sr_date(schema_data.get("dateModified", ""))

        # Tags (up to 6 per spec)
        tags = [
            a.get_text(strip=True)
            for a in soup.find_all("a", href=lambda h: h and "/tag/" in h)
            if a.get_text(strip=True)
        ]

        # Image
        image_url: Optional[str] = None
        img_el = article_el.find("img") if article_el else None
        if img_el:
            image_url = img_el.get("src") or img_el.get("data-src")
        if not image_url and schema_data:
            img = schema_data.get("image")
            if isinstance(img, dict):
                image_url = img.get("url")
            elif isinstance(img, str):
                image_url = img

        # Category — extract from URL: nova.rs/KATEGORIJA/subcat/slug/
        category: Optional[str] = None
        if schema_data:
            category = schema_data.get("articleSection") or None
        if not category:
            m = re.match(r"https?://[^/]+/([a-z][a-z-]+)/", url)
            if m and m.group(1) not in ("feed", "tag", "author", "page"):
                category = m.group(1).replace("-", " ").title()
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
