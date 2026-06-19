"""Informer.rs scraper — HTML listing + article parsing.

No RSS, no Cloudflare. 125 article links on homepage.
URL pattern: /KATEGORIJA/vesti/BROJ/SLUG
Author field contains mixed data ("Redakcija planeteNovinar17.06.202619:01") — parse name only.
Tags field has 14 tags. Related articles in [class*='related'] EXCLUDED from text.
"""
from __future__ import annotations

import re
from datetime import datetime
from typing import List, Optional

from bs4 import BeautifulSoup

from ..base import ArticleData, BaseScraper, ScraperError
from ..utils import clean_text, extract_schema_org, parse_sr_date, unique_urls

LISTING_URL = "https://www.informer.rs/"
BASE_URL = "https://www.informer.rs"

# Article URL: /KATEGORIJA/vesti/BROJ/SLUG
_ARTICLE_RE = re.compile(r"/[a-z-]+/vesti/\d+/[a-z0-9-]+/?$")

def _parse_informer_author(raw: str) -> Optional[str]:
    """Extract journalist/team name from Informer's combined author string.

    Informer appends role and timestamp directly to the name, e.g.:
      "Ekipa politikeNovinar18.06.202613:26"
      "Redakcija planeteNovinar18.06.202613:16"
      "Marko MarkovićNovinar18.06.202613:00"
      "Izvor:M.N."

    Strategy: split on "Novinar" (the role label) followed by a digit, then strip
    any remaining date fragments and known prefixes.
    """
    if not raw:
        return None
    raw = raw.strip()
    # Strip "Izvor:" / "Autor:" prefix
    raw = re.sub(r"^(?:Izvor|Autor|By)\s*:?\s*", "", raw, flags=re.IGNORECASE).strip()
    if not raw:
        return None
    # Split on "Novinar" + digit — the date runs directly into the role label
    name = re.split(r"Novinar\d", raw)[0].strip()
    # Also strip any trailing date fragment that slipped through (e.g. "18.06.2026")
    name = re.split(r"\s*\d{1,2}\.\d{2}\.\d{4}", name)[0].strip()
    return name if name else None


class InformerScraper(BaseScraper):
    SOURCE_ID = "informer"

    def get_article_urls(self) -> List[str]:
        self.logger.info("Fetching listing: %s", LISTING_URL)
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
        self.logger.info("Found %d article URLs", len(result))
        return result

    def parse_article(self, url: str) -> Optional[ArticleData]:
        self.logger.info("Parsing: %s", url)
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

        # Main content — remove related articles before extraction
        main_el = soup.find("main")
        if main_el:
            for related in main_el.find_all(class_=lambda c: c and "related" in c.lower()):
                related.decompose()
        text_raw = str(main_el) if main_el else ""
        text = clean_text(main_el) if main_el else ""

        # Author — complex parsing required
        author: Optional[str] = None
        author_el = soup.find(class_=lambda c: c and "author" in c.lower())
        if author_el:
            author = _parse_informer_author(author_el.get_text(strip=True))
        if not author and schema_data:
            a = schema_data.get("author")
            if isinstance(a, dict):
                author = a.get("name")

        # Published date — prefer schema.org (has time), fallback to HTML "17.06.2026"
        published_at: Optional[datetime] = None
        if schema_data:
            published_at = parse_sr_date(schema_data.get("datePublished", ""))
        if not published_at:
            date_el = soup.find(class_=lambda c: c and "date" in c.lower())
            if date_el:
                published_at = parse_sr_date(date_el.get_text(strip=True))

        # Category
        category: Optional[str] = None
        cat_el = soup.find(class_=lambda c: c and "categor" in c.lower())
        if cat_el:
            category = cat_el.get_text(strip=True)
        if not category and schema_data:
            category = schema_data.get("articleSection", "")
        # Fallback: from URL
        if not category:
            m = re.match(r"https?://[^/]+/([a-z-]+)/vesti/", url)
            if m:
                category = m.group(1).replace("-", " ").title()

        # Tags — a[href*='/tags/'] (up to 14)
        tags = [
            a.get_text(strip=True)
            for a in soup.find_all("a", href=lambda h: h and "/tags/" in h)
            if a.get_text(strip=True)
        ]

        # Image
        image_url: Optional[str] = None
        og_img = soup.find("meta", property="og:image")
        if og_img and og_img.get("content"):
            image_url = og_img["content"]

        # Comment count — [class*='comment'] span
        comment_count: Optional[int] = None
        cc_el = soup.find(class_=lambda c: c and "comment" in c.lower())
        if cc_el:
            span = cc_el.find("span")
            if span:
                try:
                    comment_count = int(re.sub(r"\D", "", span.get_text(strip=True)))
                except (ValueError, TypeError):
                    pass

        # Subtitle from schema.org description
        subtitle: Optional[str] = schema_data.get("description") if schema_data else None

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
            comment_count=comment_count,
            content_hash=self.content_hash(title, text),
            scraped_at=datetime.utcnow(),
            schema_data=schema_data,
        )
