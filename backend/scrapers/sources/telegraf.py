"""Telegraf.rs scraper — RSS for URLs, HTML for full article parsing."""
from __future__ import annotations

import re
from datetime import datetime
from typing import Dict, List, Optional

import feedparser
from bs4 import BeautifulSoup

from ..base import ArticleData, BaseScraper, ScraperError
from ..utils import clean_text, extract_schema_org, parse_sr_date, unique_urls

RSS_URL = "https://www.telegraf.rs/rss"
LISTING_URL = "https://www.telegraf.rs/"
BASE_URL = "https://www.telegraf.rs"


class TelegrafScraper(BaseScraper):
    SOURCE_ID = "telegraf"

    def __init__(self):
        super().__init__()
        self._rss_urls: list[str] = []

    def get_article_urls(self) -> List[str]:
        urls: list[str] = []

        # Primary: RSS (20 entries)
        try:
            self.logger.info("Fetching RSS: %s", RSS_URL)
            resp = self.fetch(RSS_URL)
            feed = feedparser.parse(resp.text)
            for entry in feed.entries:
                if hasattr(entry, "link"):
                    urls.append(entry.link)
            self.logger.info("RSS: %d entries", len(urls))
        except ScraperError as exc:
            self.logger.warning("RSS fetch failed: %s", exc)

        # Secondary: listing page (109 links on homepage)
        try:
            self.logger.info("Fetching listing: %s", LISTING_URL)
            resp = self.fetch(LISTING_URL)
            soup = BeautifulSoup(resp.text, "lxml")
            for a in soup.find_all("a", href=True):
                href = a["href"]
                if not href.startswith("http"):
                    href = BASE_URL + href if href.startswith("/") else None
                if href and "/vesti/" in href or (href and re.search(r"/[a-z-]+/[a-z0-9-]+$", href)):
                    urls.append(href)
        except ScraperError as exc:
            self.logger.warning("Listing fetch failed: %s", exc)

        SKIP_SEGMENTS = {
            "tag", "autor", "video", "teme", "page", "pretraga",
            "o-nama", "marketing", "impressum", "uslovi-koriscenja",
            "politika-privatnosti", "kontakt", "rss", "newsletter",
            "sitemap", "404", "redakcija",
        }
        SKIP_SUBSTRINGS = ["telegraf.rs/#", "telegraf.rs/?", "/feed"]

        article_urls = []
        for u in urls:
            # Prihvati samo www.telegraf.rs — ne subdomain-e (ona., auto., sport. itd.)
            if not (u.startswith("https://www.telegraf.rs") or u.startswith("http://www.telegraf.rs")):
                continue
            try:
                path = u.split("telegraf.rs", 1)[1].strip("/")
            except IndexError:
                continue
            segments = [s for s in path.split("/") if s]
            # Mora imati bar 2 segmenta (kategorija + slug)
            if len(segments) < 2:
                continue
            # Preskoci ako BILO KOJI segment pripada navigacijskim/pravnim stranama
            # (npr. /redakcija/uslovi-koriscenja, /uslovi-koriscenja/...) — ne samo prvi
            if any(seg in SKIP_SEGMENTS for seg in segments):
                continue
            if any(s in u for s in SKIP_SUBSTRINGS):
                continue
            # Dodatna zastita: pravne/navigacijske reci bilo gde u putanji
            if any(w in path.lower() for w in ("uslovi-koriscenja", "politika-privatnosti", "impressum", "uslovi-koriscenja-sajta")):
                continue
            # Slug (zadnji segment) mora biti dugačak (ne kratki navigacijski)
            slug = segments[-1]
            if len(slug) < 5:
                continue
            article_urls.append(u)

        result = unique_urls(article_urls)
        self.logger.info("Total unique article URLs: %d", len(result))
        return result

    def parse_article(self, url: str) -> Optional[ArticleData]:
        self.logger.info("Parsing: %s", url)
        try:
            resp = self.fetch(url)
        except ScraperError as exc:
            self.logger.error("Fetch failed for %s: %s", url, exc)
            return None

        soup = BeautifulSoup(resp.text, "lxml")
        schema_data = extract_schema_org(soup)

        # Title
        h1 = soup.find("h1")
        title = ""
        if h1:
            title = h1.get_text(strip=True)
        elif schema_data:
            title = schema_data.get("headline", "")
        if not title:
            og = soup.find("meta", property="og:title")
            title = og["content"].strip() if og and og.get("content") else ""

        if not title:
            self.logger.warning("No title found: %s", url)
            return None

        # Text from <main>
        main = soup.find("main")
        text_raw = str(main) if main else ""
        text = clean_text(main) if main else ""

        # Odbaci statičke stranice i listinge — nemaju datum ni dovoljno teksta
        if len(text) < 150 and not (schema_data and schema_data.get("datePublished")):
            self.logger.debug("Skipping non-article (no date, short text): %s", url)
            return None

        # Author — prefer schema.org
        author: Optional[str] = None
        if schema_data:
            a = schema_data.get("author")
            if isinstance(a, dict):
                author = a.get("name")
            elif isinstance(a, list) and a:
                author = a[0].get("name") if isinstance(a[0], dict) else str(a[0])
        if not author:
            author_el = soup.find(class_=lambda c: c and "author" in c.lower())
            if author_el:
                author = author_el.get_text(strip=True)

        # Timestamp: time[datetime] ISO8601
        published_at: Optional[datetime] = None
        updated_at: Optional[datetime] = None
        time_el = soup.find("time", attrs={"datetime": True})
        if time_el:
            published_at = parse_sr_date(time_el["datetime"])
        if not published_at and schema_data:
            published_at = parse_sr_date(schema_data.get("datePublished", ""))
        if schema_data:
            updated_at = parse_sr_date(schema_data.get("dateModified", ""))

        # Category
        category: Optional[str] = None
        cat_el = soup.find(class_=lambda c: c and "section" in c.lower())
        if cat_el:
            category = cat_el.get_text(strip=True)
        if not category and schema_data:
            category = schema_data.get("articleSection", "")

        # Tags — schema.org keywords
        tags: list[str] = []
        if schema_data:
            kw = schema_data.get("keywords", "")
            if isinstance(kw, str):
                tags = [t.strip() for t in kw.split(",") if t.strip()]
            elif isinstance(kw, list):
                tags = [str(t).strip() for t in kw if t]
        if not tags:
            tags = [
                a.get_text(strip=True)
                for a in soup.find_all("a", href=lambda h: h and "/tag/" in h)
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
            if og_img:
                image_url = og_img.get("content")

        # Comment count
        comment_count: Optional[int] = None
        cc_el = soup.find(class_=lambda c: c and "comments-count" in c.lower())
        if cc_el:
            try:
                comment_count = int(cc_el.get_text(strip=True))
            except ValueError:
                pass

        subtitle: Optional[str] = None
        if schema_data:
            subtitle = schema_data.get("description") or None

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
            comment_count=comment_count,
            content_hash=self.content_hash(title, text),
            scraped_at=datetime.utcnow(),
            schema_data=schema_data,
        )
