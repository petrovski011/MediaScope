"""RTS (rts.rs) scraper — HTML listing + article parsing.

No RSS, no Cloudflare. Listing: /page/stories/sr/ (167 links).
All content is in Cyrillic — normalize to Latin with cyrillic_to_latin().
"""
from __future__ import annotations

import re
from datetime import datetime
from typing import List, Optional

from bs4 import BeautifulSoup

from ..base import ArticleData, BaseScraper, ScraperError
from ..utils import clean_text, cyrillic_to_latin, parse_sr_date, unique_urls

LISTING_URL = "https://www.rts.rs/page/stories/sr/"
BASE_URL = "https://www.rts.rs"

# Article URL pattern: /vesti/KATEGORIJA/BROJ/NASLOV.html
_ARTICLE_RE = re.compile(r"/vesti/[^/]+/\d+/[^/]+\.html")


class RtsScraper(BaseScraper):
    SOURCE_ID = "rts"

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

        # Title — OG tag is most reliable
        og_title = soup.find("meta", property="og:title")
        title_raw = ""
        if og_title and og_title.get("content"):
            title_raw = og_title["content"].strip()
        if not title_raw:
            h1 = soup.find("h1")
            title_raw = h1.get_text(strip=True) if h1 else ""
        title = cyrillic_to_latin(title_raw)

        if not title:
            self.logger.warning("No title: %s", url)
            return None

        # Subtitle / lead
        subtitle: Optional[str] = None
        lead_el = soup.find(class_=lambda c: c and "lead" in c.lower())
        if lead_el:
            subtitle = cyrillic_to_latin(lead_el.get_text(strip=True))

        # Text — RTS has two article layouts:
        # 1. Short-story format: div.short-story-body (first one is empty placeholder — skip it)
        # 2. Full story format: div.story-wrapper with an unnamed div as body (~500w)
        content_el = None
        for candidate in soup.find_all("div", class_="short-story-body"):
            if len(candidate.get_text().split()) > 10:
                content_el = candidate
                break
        if not content_el:
            wrapper = soup.find("div", class_="story-wrapper")
            if wrapper:
                # Find the biggest direct-child div — usually the unnamed article body
                children = [d for d in wrapper.find_all("div", recursive=False)
                            if len(d.get_text().split()) > 50]
                if children:
                    content_el = max(children, key=lambda d: len(d.get_text()))
        if not content_el:
            content_el = soup.find("article") or soup.find("main")
        text_raw = str(content_el) if content_el else ""
        text = cyrillic_to_latin(clean_text(content_el)) if content_el else ""

        # Published timestamp — [class*='date'] SR_DATE format
        published_at: Optional[datetime] = None
        date_el = soup.find(class_=lambda c: c and "date" in c.lower())
        if date_el:
            published_at = parse_sr_date(cyrillic_to_latin(date_el.get_text(strip=True)))
        if not published_at:
            og_time = soup.find("meta", property="article:published_time")
            if og_time and og_time.get("content"):
                published_at = parse_sr_date(og_time["content"])

        # Category — [class*='section'], values in Cyrillic
        category: Optional[str] = None
        section_el = soup.find(class_=lambda c: c and "section" in c.lower())
        if section_el:
            category = cyrillic_to_latin(section_el.get_text(strip=True))
        # Fallback: derive from URL pattern /vesti/KATEGORIJA/
        if not category:
            m = re.search(r"/vesti/([^/]+)/", url)
            if m:
                category = m.group(1).replace("-", " ").title()

        # Image
        image_url: Optional[str] = None
        og_img = soup.find("meta", property="og:image")
        if og_img and og_img.get("content"):
            image_url = og_img["content"]
        if not image_url:
            img_el = soup.find("article") and soup.find("article").find("img")
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
