"""Juzne Vesti (juznevesti.com) scraper — STUB (403 Cloudflare blocked).

All requests to juznevesti.com return 403 Cloudflare JS challenge.
Google News RSS was tried as fallback but only provides Google News proxy URLs,
not the actual juznevesti.com article URLs — unsuitable for content extraction.
TODO: Playwright with stealth mode / undetected-chromedriver.
"""
from ..base import UnsupportedScraper


class JuzneVestiScraper(UnsupportedScraper):
    SOURCE_ID = "juzne"

    _reason = (
        "juznevesti.com returns 403 Cloudflare JS challenge for all requests. "
        "Google News RSS fallback provides only proxy URLs, not actual article content."
    )
    _suggestion = (
        "TODO: Implement with Playwright + stealth mode "
        "(playwright-stealth or undetected-chromedriver)."
    )
