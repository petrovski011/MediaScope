from __future__ import annotations

import hashlib
import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import List, Optional

import requests


class ScraperErrorType(str, Enum):
    TIMEOUT = "TIMEOUT"
    SSL_ERROR = "SSL_ERROR"
    CONNECTION_ERROR = "CONNECTION_ERROR"
    HTTP_403 = "HTTP_403"
    HTTP_429 = "HTTP_429"
    PARSE_ERROR = "PARSE_ERROR"
    BLOCKED = "BLOCKED"


class ScraperError(Exception):
    def __init__(self, error_type: ScraperErrorType, message: str):
        self.error_type = error_type
        super().__init__(f"[{error_type.value}] {message}")


@dataclass
class ArticleData:
    url: str
    source_id: str
    title: str
    subtitle: Optional[str]
    text: str
    text_raw: str
    author: Optional[str]
    published_at: Optional[datetime]
    updated_at: Optional[datetime]
    category: Optional[str]
    tags: List[str]
    image_url: Optional[str]
    image_caption: Optional[str]
    comment_count: Optional[int]
    content_hash: str
    scraped_at: datetime
    schema_data: Optional[dict]


class BaseScraper(ABC):
    SOURCE_ID: str = ""

    _RETRY_DELAYS = [2, 5, 10]
    _TIMEOUT = 15
    _HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "sr-RS,sr;q=0.9,en-US;q=0.8,en;q=0.7",
        "Accept-Encoding": "gzip, deflate",
        "DNT": "1",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
    }

    def __init__(self):
        self.logger = logging.getLogger(f"mediascope.{self.SOURCE_ID}")
        self.session = requests.Session()
        self.session.headers.update(self._HEADERS)

    def fetch(self, url: str) -> requests.Response:
        last_error: Optional[ScraperError] = None
        for attempt, delay in enumerate(self._RETRY_DELAYS, start=1):
            try:
                self.logger.debug("Fetch %s (attempt %d/%d)", url, attempt, len(self._RETRY_DELAYS))
                resp = self.session.get(url, timeout=self._TIMEOUT, allow_redirects=True)

                if resp.status_code == 403:
                    raise ScraperError(ScraperErrorType.HTTP_403, f"403 Forbidden: {url}")
                if resp.status_code == 429:
                    raise ScraperError(ScraperErrorType.HTTP_429, f"429 Too Many Requests: {url}")

                resp.raise_for_status()
                # requests defaults to ISO-8859-1 when Content-Type has no charset.
                # Serbian sites serve UTF-8 without specifying it — force correct decoding.
                ct = resp.headers.get("content-type", "").lower()
                if "text/html" in ct or "application/xml" in ct or "text/xml" in ct:
                    declared = resp.encoding or ""
                    if declared.lower().replace("-", "") in ("iso88591", "latin1", "latin-1", ""):
                        resp.encoding = "utf-8"
                self.logger.debug("OK %s — %d bytes", url, len(resp.content))
                return resp

            except ScraperError:
                raise
            except requests.exceptions.SSLError as exc:
                last_error = ScraperError(ScraperErrorType.SSL_ERROR, str(exc))
            except requests.exceptions.Timeout as exc:
                last_error = ScraperError(ScraperErrorType.TIMEOUT, str(exc))
            except requests.exceptions.ConnectionError as exc:
                last_error = ScraperError(ScraperErrorType.CONNECTION_ERROR, str(exc))
            except requests.exceptions.RequestException as exc:
                last_error = ScraperError(ScraperErrorType.CONNECTION_ERROR, str(exc))

            if attempt < len(self._RETRY_DELAYS):
                self.logger.warning("Attempt %d failed for %s — retry in %ds", attempt, url, delay)
                time.sleep(delay)

        assert last_error is not None
        raise last_error

    @abstractmethod
    def get_article_urls(self) -> List[str]:
        ...

    @abstractmethod
    def parse_article(self, url: str) -> Optional[ArticleData]:
        ...

    @staticmethod
    def content_hash(title: str, text: str) -> str:
        payload = f"{title}\x00{text}".encode("utf-8")
        return hashlib.sha256(payload).hexdigest()


class UnsupportedScraper(BaseScraper):
    """Base for scrapers that require tools beyond plain HTTP (Playwright, bypass, etc.)."""
    _reason: str = "not implemented"
    _suggestion: str = ""

    def get_article_urls(self) -> List[str]:
        self.logger.warning(
            "[%s] Scraping unavailable: %s. %s",
            self.SOURCE_ID, self._reason, self._suggestion,
        )
        return []

    def parse_article(self, url: str) -> Optional[ArticleData]:
        self.logger.warning("[%s] parse_article called but scraper is unsupported.", self.SOURCE_ID)
        return None
