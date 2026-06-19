"""Politika.rs scraper — HTML listing + article parsing.

Homepage has 160 article links. /sr/lat/ listing returns 404 — use homepage.
Article URL pattern: /scc/clanak/BROJ/SLUG
Cloudflare present but medium risk — BeautifulSoup works on homepage.
Historic daily newspaper — high-priority source.
"""
from __future__ import annotations

import re
import time
from datetime import datetime
from typing import List, Optional

from bs4 import BeautifulSoup

from ..base import ArticleData, BaseScraper, ScraperError
from ..utils import clean_text, extract_schema_org, parse_sr_date, cyrillic_to_latin, unique_urls

LISTING_URL = "https://www.politika.rs/"
BASE_URL = "https://www.politika.rs"

# Article URL: /scc/clanak/BROJ/SLUG — matches both relative and absolute hrefs
_ARTICLE_RE = re.compile(r"(?:politika\.rs)?/scc/clanak/\d+")
# Matches "Četvrtak, 18.06.2026. u 08:40" in the article header byline element
_POL_DATE_RE = re.compile(r"\d{1,2}\.\d{1,2}\.\d{4}\.\s+u\s+\d{2}:\d{2}")


class PolitikaScraper(BaseScraper):
    SOURCE_ID = "politika"

    def get_article_urls(self) -> List[str]:
        self.logger.info("Fetching listing (homepage): %s", LISTING_URL)
        try:
            resp = self.fetch(LISTING_URL)
        except ScraperError as exc:
            self.logger.error("Listing fetch failed: %s", exc)
            return []

        soup = BeautifulSoup(resp.content, "lxml")
        urls: list[str] = []
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if _ARTICLE_RE.search(href):
                # Strip anchor fragments
                href = href.split("#")[0]
                full = href if href.startswith("http") else BASE_URL + href
                urls.append(full)

        result = unique_urls(urls)
        self.logger.info("Found %d article URLs", len(result))
        return result

    def parse_article(self, url: str) -> Optional[ArticleData]:
        self.logger.info("Parsing: %s", url)
        time.sleep(1.0)  # politika.rs rate-limits aggressive sequential fetching → 429
        try:
            resp = self.fetch(url)
        except ScraperError as exc:
            self.logger.error("Fetch failed: %s — %s", url, exc)
            return None

        soup = BeautifulSoup(resp.content, "lxml")
        schema_data = extract_schema_org(soup)

        # Title — may be in Cyrillic, normalize to Latin
        h1 = soup.find("h1")
        title_raw = h1.get_text(strip=True) if h1 else ""
        if not title_raw and schema_data:
            title_raw = schema_data.get("headline", "")
        if not title_raw:
            og = soup.find("meta", property="og:title")
            title_raw = og["content"].strip() if og and og.get("content") else ""
        title = cyrillic_to_latin(title_raw)

        if not title:
            self.logger.warning("No title: %s", url)
            return None

        # Subtitle
        subtitle: Optional[str] = None
        lead_el = soup.find(class_=lambda c: c and "lead" in c.lower())
        if lead_el:
            subtitle = cyrillic_to_latin(lead_el.get_text(strip=True))
        if not subtitle and schema_data:
            subtitle = schema_data.get("description") or None

        # Text — article body
        content_el = (
            soup.find(class_=lambda c: c and "article-body" in c.lower())
            or soup.find(class_=lambda c: c and "article-content" in c.lower())
            or soup.find(class_=lambda c: c and "articleBody" in (c or ""))
            or soup.find("article")
            or soup.find("main")
        )
        text_raw = str(content_el) if content_el else ""
        text = cyrillic_to_latin(clean_text(content_el)) if content_el else ""

        # Author + Timestamp — Politika's byline element contains both date and author
        # e.g. "Četvrtak, 18.06.2026. u 08:40Politika onlajn"
        author: Optional[str] = None
        published_at: Optional[datetime] = None
        author_el = soup.find(class_=lambda c: c and "author" in c.lower())
        if author_el:
            raw = cyrillic_to_latin(author_el.get_text(strip=True))
            m_date = _POL_DATE_RE.search(raw)
            if m_date:
                # Parse date from "18.06.2026. u 08:40" — convert to ISO for parse_sr_date
                date_str = m_date.group(0).replace(". u ", "T").replace(".", "-", 2).replace(".", "")
                # Simpler: just pass the extracted substring directly
                date_raw = m_date.group(0)  # "18.06.2026. u 08:40"
                dt_iso = re.sub(
                    r"(\d{2})\.(\d{2})\.(\d{4})\.\s+u\s+(\d{2}:\d{2})",
                    r"\3-\2-\1T\4",
                    date_raw,
                )
                published_at = parse_sr_date(dt_iso)
                # Strip day name + date from byline to get just the author
                clean = _POL_DATE_RE.sub("", raw)
                clean = re.sub(r"^[^,]+,\s*", "", clean).strip()  # strip "Četvrtak, "
                author = clean if clean else None
        if not author and schema_data:
            a_field = schema_data.get("author")
            if isinstance(a_field, dict):
                author = a_field.get("name")
        if not published_at and schema_data:
            published_at = parse_sr_date(schema_data.get("datePublished", ""))
        if not published_at:
            time_el = soup.find("time", attrs={"datetime": True})
            if time_el:
                published_at = parse_sr_date(time_el["datetime"])
        if not published_at:
            og_time = soup.find("meta", property="article:published_time")
            if og_time and og_time.get("content"):
                published_at = parse_sr_date(og_time["content"])

        updated_at: Optional[datetime] = None
        if schema_data:
            updated_at = parse_sr_date(schema_data.get("dateModified", ""))

        # Category — from URL /scc/clanak/BROJ/KATEGORIJA/... or schema
        category: Optional[str] = None
        m = re.search(r"/scc/clanak/\d+/([^/]+)/", url)
        if m:
            category = m.group(1).replace("-", " ").title()
        if not category and schema_data:
            category = schema_data.get("articleSection", "") or None

        # Tags — politika.rs tags are in Cyrillic, normalize to Latin
        tags = [
            cyrillic_to_latin(a.get_text(strip=True))
            for a in soup.find_all("a", href=lambda h: h and "/tag" in h)
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
