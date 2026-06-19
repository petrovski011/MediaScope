"""Mondo.rs scraper — HTML listing (SSR Nuxt.js) + article parsing.

Homepage is server-side rendered — BeautifulSoup finds 50+ article links.
Article URL pattern: /SECTION/SUBSECTION/aID/slug.html
Date format: "18.06.2026. 10:09h" — handled by parse_sr_date.
"""
from __future__ import annotations

import re
from datetime import datetime
from typing import List, Optional

from bs4 import BeautifulSoup

from ..base import ArticleData, BaseScraper, ScraperError
from ..utils import clean_text, extract_schema_org, parse_sr_date, unique_urls

LISTING_URL = "https://www.mondo.rs/"
BASE_URL = "https://www.mondo.rs"

# Article URL: /SECTION/SUBSECTION/aID/slug.html — article ID has 'a' prefix
_ARTICLE_RE = re.compile(r"/[A-Za-z][A-Za-z0-9/_-]*/a\d{5,}/[a-z0-9-]+\.html")

# Mondo author element: "Prenosi:Author NameObjavljeno 18.06.2026. 7:33h1..."
_AUTHOR_PREFIX_RE = re.compile(r"^(?:Prenosi:|Autor:?|Piše:?)\s*", re.IGNORECASE)


class MondoScraper(BaseScraper):
    SOURCE_ID = "mondo"

    def get_article_urls(self) -> List[str]:
        self.logger.info("Fetching listing: %s", LISTING_URL)
        try:
            resp = self.fetch(LISTING_URL)
        except ScraperError as exc:
            self.logger.error("Listing fetch failed: %s", exc)
            return []

        soup = BeautifulSoup(resp.content, "lxml")
        urls: list[str] = []
        for a in soup.find_all("a", href=True):
            href = a["href"].split("?")[0].split("#")[0]
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

        # Subtitle — .lead element or og:description
        subtitle: Optional[str] = None
        lead_el = soup.find(class_=lambda c: c and "lead" in c.lower())
        if lead_el:
            t = lead_el.get_text(strip=True)
            if len(t) > 20:
                subtitle = t
        if not subtitle:
            og_desc = soup.find("meta", property="og:description")
            if og_desc and og_desc.get("content") and len(og_desc["content"]) > 20:
                subtitle = og_desc["content"].strip()

        # Content — div.article-body
        content_el = (
            soup.find(class_=lambda c: c and "article-body" in c.lower())
            or soup.find("article")
            or soup.find("main")
        )
        text_raw = str(content_el) if content_el else ""
        text = clean_text(content_el) if content_el else ""

        # Date — <time class="article-header-date-published">Objavljeno 18.06.2026. 10:09h</time>
        published_at: Optional[datetime] = None
        time_el = soup.find("time", class_=lambda c: c and "date-published" in (c or ""))
        if time_el:
            raw_date = time_el.get_text(strip=True)
            raw_date = re.sub(r"^Objavljeno\s*", "", raw_date, flags=re.IGNORECASE)
            published_at = parse_sr_date(raw_date)
        if not published_at:
            time_el2 = soup.find("time", attrs={"datetime": True})
            if time_el2:
                published_at = parse_sr_date(time_el2["datetime"])
        if not published_at and schema_data:
            published_at = parse_sr_date(schema_data.get("datePublished", ""))

        updated_at: Optional[datetime] = None
        time_mod = soup.find("time", class_=lambda c: c and "date-modified" in (c or ""))
        if time_mod:
            raw_mod = re.sub(r"^Izmenjeno\s*", "", time_mod.get_text(strip=True), flags=re.IGNORECASE)
            updated_at = parse_sr_date(raw_mod)
        if not updated_at and schema_data:
            updated_at = parse_sr_date(schema_data.get("dateModified", ""))

        # Author — "Prenosi:Marina LetićObjavljeno 18.06.2026. 7:33h1..."
        author: Optional[str] = None
        author_el = soup.find(class_=lambda c: c and "author" in (c or "").lower())
        if author_el:
            raw = author_el.get_text(strip=True)
            # Strip everything from "Objavljeno" onwards (date + junk)
            raw = re.split(r"Objavljeno|Izmenjeno|\d{2}\.\d{2}\.\d{4}", raw)[0]
            raw = _AUTHOR_PREFIX_RE.sub("", raw).strip()
            author = raw if raw and len(raw) < 100 else None
        if not author and schema_data:
            a_field = schema_data.get("author")
            if isinstance(a_field, dict):
                author = a_field.get("name")

        # Category — from URL: /SECTION/SUBSECTION/aID/ → use SUBSECTION
        category: Optional[str] = None
        m = re.search(r"/([A-Za-z][A-Za-z0-9-]*)/a\d+/", url)
        if m:
            category = m.group(1).replace("-", " ").title()

        # Tags
        tags = [
            a.get_text(strip=True)
            for a in soup.find_all("a", href=lambda h: h and "/tag" in h.lower())
            if a.get_text(strip=True)
        ]

        # Image
        image_url: Optional[str] = None
        og_img = soup.find("meta", property="og:image")
        if og_img and og_img.get("content"):
            image_url = og_img["content"]
        if not image_url and schema_data:
            img = schema_data.get("image")
            if isinstance(img, dict):
                image_url = img.get("url")
            elif isinstance(img, str):
                image_url = img

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
