"""Pink.rs scraper — HTML listing + article parsing.

No Cloudflare, no RSS. 40 article links on homepage.
URL pattern: /KATEGORIJA/BROJ/SLUG
"""
from __future__ import annotations

import re
from datetime import datetime
from typing import List, Optional

from bs4 import BeautifulSoup

from ..base import ArticleData, BaseScraper, ScraperError
from ..utils import clean_text, extract_schema_org, parse_sr_date, unique_urls

LISTING_URL = "https://pink.rs/"
BASE_URL = "https://pink.rs"

# Article URL: /KATEGORIJA/BROJ/SLUG — matches both relative and absolute hrefs
_ARTICLE_RE = re.compile(r"(?:pink\.rs)?/[a-z][a-z-]+/\d{4,}/[a-z0-9-]")


class PinkScraper(BaseScraper):
    SOURCE_ID = "pink"

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

        # Text — pink.rs has no <article> tag; content is in div.news-single-content
        content_el = (
            soup.select_one("div.news-single-content")
            or soup.find(class_=lambda c: c and "article-body" in c.lower())
            or soup.find(class_=lambda c: c and "entry-content" in c.lower())
            or soup.find("main")
        )
        if content_el:
            # Remove related-news widget embedded in the article body
            for rm in content_el.find_all(class_=lambda c: c and "related" in " ".join(c if isinstance(c, list) else [c]).lower()):
                rm.decompose()
        text_raw = str(content_el) if content_el else ""
        text = clean_text(content_el) if content_el else ""

        # Author
        author: Optional[str] = None
        author_el = soup.find(class_=lambda c: c and "author" in c.lower())
        if author_el:
            author = author_el.get_text(strip=True)
        if not author and schema_data:
            a = schema_data.get("author")
            if isinstance(a, dict):
                author = a.get("name")

        # Timestamp
        published_at: Optional[datetime] = None
        if schema_data:
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

        # Category from URL: /KATEGORIJA/BROJ/SLUG
        category: Optional[str] = None
        m = re.match(r"https?://[^/]+/([^/]+)/\d+/", url)
        if m:
            category = m.group(1).replace("-", " ").title()

        # Tags — strip leading "#" from tag strings (pink.rs uses "#tag" format)
        tags = [
            a.get_text(strip=True).lstrip("#").strip()
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

        subtitle: Optional[str] = None
        if schema_data:
            subtitle = schema_data.get("description") or None
        if not subtitle:
            og_desc = soup.find("meta", property="og:description")
            if og_desc and og_desc.get("content") and len(og_desc["content"]) > 20:
                subtitle = og_desc["content"].strip()

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
