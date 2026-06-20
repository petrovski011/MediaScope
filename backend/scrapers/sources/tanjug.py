"""Tanjug.rs scraper — HTML listing + article parsing.

STATE NEWS AGENCY — flag all articles as high-priority origin tracking.
No RSS, no Cloudflare. 39 article links on homepage.
URL pattern: /KATEGORIJA/podkat/BROJ/SLUG/vest
Tags are concatenated without separators — require smart splitting.
"""
from __future__ import annotations

import re
from datetime import datetime
from typing import List, Optional

from bs4 import BeautifulSoup

from ..base import ArticleData, BaseScraper, ScraperError
from ..utils import clean_text, extract_schema_org, parse_sr_date, unique_urls

LISTING_URL = "https://www.tanjug.rs/"
BASE_URL = "https://www.tanjug.rs"

# Article URL: /KATEGORIJA/podkat/BROJ/SLUG/vest
_ARTICLE_RE = re.compile(r"/[a-z-]+/[a-z-]+/\d+/[a-z0-9-]+/vest/?$")

# Tanjug author field often "Izvor: TANJUG" — extract source name
_TANJUG_AUTHOR_RE = re.compile(r"(?:Izvor|Autor|By):\s*(.+)", re.IGNORECASE)

# Tags are concatenated: "Aleksandar VučićDunavNovi Sad"
# Split on capitalized words / known delimiters
_TAG_SPLIT_RE = re.compile(r"(?<=[a-zčćžšđ])(?=[A-ZČĆŽŠĐ])")


def _split_concatenated_tags(raw: str) -> list[str]:
    """Split a concatenated tag string like 'Aleksandar VučićDunavNovi Sad'."""
    if not raw:
        return []
    # Split on uppercase letters that immediately follow lowercase
    parts = _TAG_SPLIT_RE.split(raw)
    return [p.strip() for p in parts if p.strip()]


def _parse_tanjug_author(raw: str) -> Optional[str]:
    if not raw:
        return None
    raw = raw.strip()
    m = _TANJUG_AUTHOR_RE.match(raw)
    name = m.group(1).strip() if m else raw
    if not name:
        return None
    # Normalize all-caps names: "TANJUG" → "Tanjug", "MILAN POPOVIC" → "Milan Popovic"
    if not any(c.islower() for c in name):
        name = name.title()
    return name


class TanjugScraper(BaseScraper):
    SOURCE_ID = "tanjug"

    # NOTE: Tanjug is the Serbian state news agency (državna novinska agencija).
    # All its articles are critical for origin tracking — do not skip any.

    def get_article_urls(self) -> List[str]:
        self.logger.info("Fetching listing (homepage): %s", LISTING_URL)
        try:
            resp = self.fetch(LISTING_URL)
        except ScraperError as exc:
            self.logger.error("Listing fetch failed: %s", exc)
            return []

        soup = BeautifulSoup(resp.text, "lxml")
        urls: list[str] = []
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if _ARTICLE_RE.search(href):
                full = href if href.startswith("http") else BASE_URL + href
                urls.append(full)

        result = unique_urls(urls)
        self.logger.info("Found %d article URLs (Tanjug — state agency)", len(result))
        return result

    def parse_article(self, url: str) -> Optional[ArticleData]:
        self.logger.info("Parsing [STATE AGENCY]: %s", url)
        try:
            resp = self.fetch(url)
        except ScraperError as exc:
            self.logger.error("Fetch failed: %s — %s", url, exc)
            return None

        soup = BeautifulSoup(resp.text, "lxml")
        schema_data = extract_schema_org(soup)

        # Title
        title_el = soup.find("h1", class_=lambda c: c and "single-news-title" in c.lower())
        if not title_el:
            title_el = soup.find("h1")
        title = title_el.get_text(strip=True) if title_el else ""
        if not title and schema_data:
            title = schema_data.get("headline", "")
        if not title:
            og = soup.find("meta", property="og:title")
            title = og["content"].strip() if og and og.get("content") else ""

        if not title:
            self.logger.warning("No title: %s", url)
            return None

        # Subtitle / lead
        subtitle: Optional[str] = None
        lead_el = soup.find(class_=lambda c: c and "lead" in c.lower())
        if lead_el:
            subtitle = lead_el.get_text(strip=True)

        # Text from <main>
        main_el = soup.find("main")
        text_raw = str(main_el) if main_el else ""
        text = clean_text(main_el) if main_el else ""

        # Author — "Izvor: TANJUG" pattern
        author: Optional[str] = None
        author_el = soup.find(class_=lambda c: c and "author" in c.lower())
        if author_el:
            author = _parse_tanjug_author(author_el.get_text(strip=True))
        if not author and schema_data:
            a = schema_data.get("author")
            if isinstance(a, dict):
                author = a.get("name")

        # Published timestamp — article:published_time has exact datetime (e.g. "2026-06-20 13:28:00")
        published_at: Optional[datetime] = None
        og_pub = soup.find("meta", property="article:published_time")
        if og_pub and og_pub.get("content"):
            published_at = parse_sr_date(og_pub["content"])
        if not published_at and schema_data:
            published_at = parse_sr_date(schema_data.get("datePublished", ""))
        if not published_at:
            date_el = soup.find(class_=lambda c: c and "single-news-time" in c.lower())
            if date_el:
                published_at = parse_sr_date(date_el.get_text(strip=True))

        # Category
        category: Optional[str] = None
        cat_el = soup.find(class_=lambda c: c and "categor" in c.lower())
        if cat_el:
            category = cat_el.get_text(strip=True)
        if not category:
            m = re.match(r"https?://[^/]+/([a-z-]+)/", url)
            if m:
                category = m.group(1).replace("-", " ").title()

        # Tags — tanjug.rs wraps each tag in an <a> inside div.single-news-tags.
        # Using get_text() concatenates them without separators; use find_all("a") instead.
        tags: list[str] = []
        tag_el = soup.find(class_=lambda c: c and "tag" in c.lower())
        if tag_el:
            tags = [a.get_text(strip=True) for a in tag_el.find_all("a") if a.get_text(strip=True)]
        if not tags and schema_data:
            kw = schema_data.get("keywords", "")
            if isinstance(kw, str):
                tags = [t.strip() for t in kw.split(",") if t.strip()]

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
            updated_at=None,
            category=category,
            tags=tags,
            image_url=image_url,
            image_caption=None,
            comment_count=None,
            content_hash=self.content_hash(title, text),
            scraped_at=datetime.utcnow(),
            schema_data=schema_data,
        )
