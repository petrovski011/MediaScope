#!/usr/bin/env python3
"""
MediaScope - Tehnicka analiza srpskih medijskih sajtova
Pokretanje: pip install requests beautifulsoup4 lxml feedparser && python3 mediascope_analyze.py
Rezultati se cuvaju u mediascope_analiza_TIMESTAMP.csv i .json
Log se cuva u mediascope_analiza_TIMESTAMP.log
"""

import requests
import feedparser
import json
import csv
import time
import re
import sys
import logging
import traceback
from datetime import datetime
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from requests.exceptions import (
    Timeout, ConnectionError, SSLError, TooManyRedirects,
    HTTPError, RequestException
)

# ── Logging setup ─────────────────────────────────────────────────────────────

TIMESTAMP = datetime.now().strftime("%Y%m%d_%H%M%S")
LOG_PATH = f"mediascope_analiza_{TIMESTAMP}.log"

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_PATH, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ]
)
log = logging.getLogger("mediascope")

# ── Konstante ─────────────────────────────────────────────────────────────────

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
HEADERS = {
    "User-Agent": UA,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "sr,en-US;q=0.7,en;q=0.3",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
}
TIMEOUT = 15
MAX_RETRIES = 3
RETRY_DELAYS = [2, 5, 10]
INTER_SITE_DELAY = 2

# ── Sajtovi ───────────────────────────────────────────────────────────────────

SITES = [
    {"id": "n1",       "name": "N1",          "url": "https://n1info.rs",          "listing": "https://n1info.rs/vesti/",             "rss_candidates": ["https://n1info.rs/feed/", "https://n1info.rs/rss/"]},
    {"id": "blic",     "name": "Blic",         "url": "https://www.blic.rs",        "listing": "https://www.blic.rs/najnovije",        "rss_candidates": ["https://www.blic.rs/feed/", "https://www.blic.rs/rss/", "https://www.blic.rs/rss"]},
    {"id": "telegraf", "name": "Telegraf",     "url": "https://www.telegraf.rs",   "listing": "https://www.telegraf.rs/",              "rss_candidates": ["https://www.telegraf.rs/feed/", "https://www.telegraf.rs/rss"]},
    {"id": "kurir",    "name": "Kurir",        "url": "https://www.kurir.rs",       "listing": "https://www.kurir.rs/najnovije-vesti", "rss_candidates": ["https://www.kurir.rs/feed/", "https://www.kurir.rs/rss"]},
    {"id": "sd",       "name": "Srbija danas", "url": "https://www.sd.rs",          "listing": "https://www.sd.rs/",                   "rss_candidates": ["https://www.sd.rs/feed/", "https://www.sd.rs/rss"]},
    {"id": "rts",      "name": "RTS",          "url": "https://www.rts.rs",         "listing": "https://www.rts.rs/page/stories/sr/",  "rss_candidates": ["https://www.rts.rs/rss/sr.html", "https://www.rts.rs/feed/"]},
    {"id": "nova",     "name": "Nova",         "url": "https://nova.rs",            "listing": "https://nova.rs/vesti/",               "rss_candidates": ["https://nova.rs/feed/", "https://nova.rs/rss/"]},
    {"id": "informer", "name": "Informer",     "url": "https://informer.rs",        "listing": "https://informer.rs/",                 "rss_candidates": ["https://informer.rs/rss", "https://informer.rs/feed/"]},
    {"id": "danas",    "name": "Danas",        "url": "https://www.danas.rs",       "listing": "https://www.danas.rs/najnovije-vesti/","rss_candidates": ["https://www.danas.rs/feed/", "https://www.danas.rs/rss/"]},
    {"id": "b92",      "name": "B92",          "url": "https://www.b92.net",        "listing": "https://www.b92.net/info/vesti/",       "rss_candidates": ["https://www.b92.net/rss/", "https://www.b92.net/feed/"]},
    {"id": "mondo",    "name": "Mondo",        "url": "https://mondo.rs",           "listing": "https://mondo.rs/Info/Srbija/",         "rss_candidates": ["https://mondo.rs/feed/", "https://mondo.rs/rss/"]},
    {"id": "pink",     "name": "Pink",         "url": "https://pink.rs",            "listing": "https://pink.rs/vesti/",               "rss_candidates": ["https://pink.rs/feed/", "https://pink.rs/rss/"]},
    {"id": "birn",     "name": "BIRN",         "url": "https://birn.rs",            "listing": "https://birn.rs/vesti/",               "rss_candidates": ["https://birn.rs/feed/", "https://birn.rs/rss/"]},
    {"id": "radar",    "name": "Radar",        "url": "https://radar.rs",           "listing": "https://radar.rs/vesti/",              "rss_candidates": ["https://radar.rs/feed/", "https://radar.rs/rss/"]},
    {"id": "prva",     "name": "Prva TV",      "url": "https://www.prva.rs",        "listing": "https://www.prva.rs/vesti/",           "rss_candidates": ["https://www.prva.rs/feed/", "https://www.prva.rs/rss/"]},
    {"id": "juzne",    "name": "Juzne vesti",  "url": "https://www.juznevesti.com", "listing": "https://www.juznevesti.com/",           "rss_candidates": ["https://www.juznevesti.com/feed/", "https://www.juznevesti.com/rss/"]},
    {"id": "vreme",    "name": "Vreme",        "url": "https://www.vreme.rs",       "listing": "https://www.vreme.rs/vesti/",          "rss_candidates": ["https://www.vreme.rs/feed/", "https://www.vreme.rs/rss/"]},
    {"id": "insajder", "name": "Insajder",     "url": "https://insajder.net",       "listing": "https://insajder.net/vesti/",          "rss_candidates": ["https://insajder.net/feed/", "https://insajder.net/rss/"]},
    {"id": "tanjug",   "name": "Tanjug",       "url": "https://www.tanjug.rs",      "listing": "https://www.tanjug.rs/vesti/",         "rss_candidates": ["https://www.tanjug.rs/feed/", "https://www.tanjug.rs/rss"]},
    {"id": "politika", "name": "Politika",     "url": "https://www.politika.rs",    "listing": "https://www.politika.rs/sr/lat/",      "rss_candidates": ["https://www.politika.rs/feed/", "https://www.politika.rs/rss"]},
]

# ── Error klasifikacija ───────────────────────────────────────────────────────

def classify_error(e):
    """Klasifikuj tip greske za laksu dijagnozu."""
    if isinstance(e, Timeout):
        return "TIMEOUT"
    elif isinstance(e, SSLError):
        return "SSL_ERROR"
    elif isinstance(e, ConnectionError):
        return "CONNECTION_ERROR"
    elif isinstance(e, TooManyRedirects):
        return "TOO_MANY_REDIRECTS"
    elif isinstance(e, HTTPError):
        return f"HTTP_{e.response.status_code}" if e.response else "HTTP_ERROR"
    elif isinstance(e, RequestException):
        return "REQUEST_ERROR"
    elif isinstance(e, json.JSONDecodeError):
        return "JSON_PARSE_ERROR"
    elif isinstance(e, Exception):
        return type(e).__name__
    return "UNKNOWN_ERROR"

# ── Fetch sa retry i error logovanjem ────────────────────────────────────────

def fetch(url, timeout=TIMEOUT, label=""):
    """
    Fetchuj URL sa retry logikom i detaljnim logovanjem.
    Vraca (response, error_info) tuple.
    error_info je None ako je uspesno, dict ako je doslo do greske.
    """
    last_error = None
    last_error_type = None

    for attempt in range(MAX_RETRIES):
        try:
            log.debug(f"  Fetch [{label}] attempt {attempt+1}/{MAX_RETRIES}: {url}")
            start = time.time()
            r = requests.get(url, headers=HEADERS, timeout=timeout, allow_redirects=True)
            elapsed = time.time() - start

            if attempt > 0:
                log.info(f"  Fetch uspeo na pokuseaju {attempt+1}: {url}")

            # Loguj ne-200 statuse ali ih ne tretuj kao gresku odmah
            if r.status_code != 200:
                log.warning(f"  HTTP {r.status_code} za {url}")

            return r, None

        except Exception as e:
            last_error = e
            last_error_type = classify_error(e)
            log.warning(f"  Fetch greska attempt {attempt+1} [{last_error_type}]: {url} - {e}")

            if attempt < MAX_RETRIES - 1:
                delay = RETRY_DELAYS[attempt]
                log.debug(f"  Cekam {delay}s pre retry...")
                time.sleep(delay)

    # Svi pokusaji su failali
    error_info = {
        "error_type": last_error_type,
        "error_message": str(last_error),
        "error_traceback": traceback.format_exc(),
        "attempts": MAX_RETRIES,
        "url": url,
    }
    log.error(f"  Fetch kompletno failao nakon {MAX_RETRIES} pokusaja [{last_error_type}]: {url}")
    return None, error_info

# ── Analiticki moduli ─────────────────────────────────────────────────────────

def check_rss(candidates, site_name):
    result = {
        "rss_status": "not_found",
        "rss_url": None,
        "rss_error": None,
        "rss_error_type": None,
        "rss_entries_count": 0,
        "rss_has_dates": False,
        "rss_has_content": False,
        "rss_sample_title": "",
        "rss_checked_urls": [],
    }

    for url in candidates:
        result["rss_checked_urls"].append(url)
        r, err = fetch(url, timeout=10, label=f"RSS {site_name}")

        if err:
            result["rss_error"] = err["error_message"]
            result["rss_error_type"] = err["error_type"]
            log.debug(f"  RSS kandidat failao [{err['error_type']}]: {url}")
            continue

        if r.status_code != 200:
            log.debug(f"  RSS kandidat HTTP {r.status_code}: {url}")
            continue

        ct = r.headers.get("Content-Type", "")
        content_start = r.text[:500]

        is_feed = (
            any(x in ct for x in ["xml", "rss", "atom"])
            or any(x in content_start for x in ["<rss", "<feed", "<channel", "<?xml"])
        )

        if not is_feed:
            log.debug(f"  RSS kandidat nije feed format: {url} (CT: {ct})")
            continue

        try:
            feed = feedparser.parse(r.content)
            if feed.bozo and not feed.entries:
                log.warning(f"  RSS parse greska (bozo): {url} - {feed.bozo_exception}")
                result["rss_error"] = str(feed.bozo_exception)
                result["rss_error_type"] = "RSS_PARSE_ERROR"
                continue

            result["rss_status"] = "confirmed"
            result["rss_url"] = url
            result["rss_entries_count"] = len(feed.entries)
            result["rss_error"] = None
            result["rss_error_type"] = None

            if feed.entries:
                entry = feed.entries[0]
                result["rss_has_dates"] = bool(entry.get("published") or entry.get("updated"))
                result["rss_has_content"] = bool(entry.get("summary") or entry.get("content"))
                result["rss_sample_title"] = entry.get("title", "")[:80]

            log.info(f"  RSS pronadjen: {url} ({len(feed.entries)} entries)")
            return result

        except Exception as e:
            log.warning(f"  RSS feedparser exception: {url} - {e}")
            result["rss_error"] = str(e)
            result["rss_error_type"] = classify_error(e)

    if result["rss_status"] == "not_found":
        log.info(f"  RSS nije pronadjen ni na jednom od {len(candidates)} kandidata")

    return result


def check_wordpress(base_url, soup):
    result = {
        "is_wordpress": False,
        "wordpress_version": None,
        "wp_api_available": False,
        "wp_api_url": None,
        "wp_api_error": None,
        "wp_api_error_type": None,
        "wp_detection_signals": [],
    }

    gen = soup.find("meta", attrs={"name": "generator"})
    if gen and "wordpress" in gen.get("content", "").lower():
        result["is_wordpress"] = True
        result["wp_detection_signals"].append("generator_meta")
        ver = re.search(r"WordPress\s+([\d.]+)", gen.get("content", ""), re.I)
        if ver:
            result["wordpress_version"] = ver.group(1)

    if soup.find("link", rel=lambda r: r and "api.w.org" in str(r)):
        result["is_wordpress"] = True
        result["wp_detection_signals"].append("api_w_org_link")

    html_str = str(soup)
    if "wp-content" in html_str:
        result["is_wordpress"] = True
        result["wp_detection_signals"].append("wp-content")
    if "wp-includes" in html_str:
        result["is_wordpress"] = True
        result["wp_detection_signals"].append("wp-includes")

    if result["is_wordpress"]:
        api_url = base_url.rstrip("/") + "/wp-json/wp/v2/posts?per_page=1"
        r, err = fetch(api_url, timeout=8, label="WP API")

        if err:
            result["wp_api_error"] = err["error_message"]
            result["wp_api_error_type"] = err["error_type"]
            log.warning(f"  WP API fetch greska [{err['error_type']}]: {api_url}")
        elif r.status_code == 200:
            try:
                data = r.json()
                if isinstance(data, list) and len(data) > 0:
                    result["wp_api_available"] = True
                    result["wp_api_url"] = base_url.rstrip("/") + "/wp-json/wp/v2/posts"
                    log.info(f"  WP API dostupan: {result['wp_api_url']}")
            except json.JSONDecodeError as e:
                result["wp_api_error"] = f"JSON parse greska: {e}"
                result["wp_api_error_type"] = "JSON_PARSE_ERROR"
                log.warning(f"  WP API JSON greska: {api_url} - {e}")
        else:
            log.debug(f"  WP API HTTP {r.status_code}: {api_url}")

    return result


def check_js_rendering(soup, response_text):
    result = {
        "has_react_root": False,
        "has_next_js": False,
        "has_nuxt": False,
        "has_angular": False,
        "has_vue": False,
        "has_noscript_warning": False,
        "content_in_html": False,
        "js_rendering_risk": "low",
        "js_signals": [],
    }

    text = response_text[:50000]

    if soup.find("div", id="root") or soup.find("div", id="app"):
        result["has_react_root"] = True
        result["js_signals"].append("react_root_div")
    if "__NEXT_DATA__" in text or "_next/static" in text:
        result["has_next_js"] = True
        result["js_signals"].append("nextjs")
    if "__NUXT__" in text or "/_nuxt/" in text:
        result["has_nuxt"] = True
        result["js_signals"].append("nuxt")
    if "ng-version" in text or "ng-app" in text:
        result["has_angular"] = True
        result["js_signals"].append("angular")
    if "__vue__" in text or "data-v-app" in text:
        result["has_vue"] = True
        result["js_signals"].append("vue")

    noscript = soup.find("noscript")
    if noscript and len(noscript.get_text(strip=True)) > 20:
        result["has_noscript_warning"] = True
        result["js_signals"].append("noscript_warning")

    articles = soup.find_all(["article", "h2", "h3"], limit=10)
    result["content_in_html"] = len(articles) >= 3

    js_count = sum([
        result["has_react_root"], result["has_next_js"],
        result["has_nuxt"], result["has_angular"], result["has_vue"],
    ])

    if js_count >= 2 or (js_count >= 1 and not result["content_in_html"]):
        result["js_rendering_risk"] = "high"
    elif js_count == 1 or not result["content_in_html"]:
        result["js_rendering_risk"] = "medium"

    return result


def check_timestamps(soup):
    result = {
        "og_published_time": False,
        "og_updated_time": False,
        "article_published_time": False,
        "schema_date_published": False,
        "time_element": False,
        "timestamp_reliability": "none",
        "sample_timestamp": None,
        "timestamp_format": None,
    }

    for prop in ["og:published_time", "article:published_time"]:
        meta = soup.find("meta", property=prop)
        if meta and meta.get("content"):
            result["og_published_time"] = True
            result["article_published_time"] = True
            ts = meta["content"]
            result["sample_timestamp"] = ts
            # Detektuj format
            if "T" in ts and ("+" in ts or "Z" in ts):
                result["timestamp_format"] = "ISO8601_with_timezone"
            elif "T" in ts:
                result["timestamp_format"] = "ISO8601_no_timezone"
            else:
                result["timestamp_format"] = "other"

    meta = soup.find("meta", property="og:updated_time")
    if meta and meta.get("content"):
        result["og_updated_time"] = True

    html_str = str(soup)
    if '"datePublished"' in html_str or "'datePublished'" in html_str:
        result["schema_date_published"] = True

    if soup.find("time"):
        result["time_element"] = True

    if result["og_published_time"] and result["og_updated_time"]:
        result["timestamp_reliability"] = "high"
    elif result["og_published_time"] or result["schema_date_published"]:
        result["timestamp_reliability"] = "medium"
    elif result["time_element"]:
        result["timestamp_reliability"] = "low"

    return result


def check_paywall(soup, response_text):
    text = response_text.lower()
    sr_keywords = ["pretplata", "pretplatite", "clanstvo", "premium sadrzaj",
                   "registrujte se", "prijavite se da biste", "samo za pretplatnike"]
    en_keywords = ["paywall", "subscribe to read", "subscription required",
                   "members only", "premium content"]

    found_sr = [kw for kw in sr_keywords if kw in text]
    found_en = [kw for kw in en_keywords if kw in text]
    all_found = found_sr + found_en

    schema_paywall = (
        '"isAccessibleForFree"' in response_text
        and ('"False"' in response_text or '"false"' in response_text)
    )

    meta_paywall = soup.find("meta", attrs={"name": "paywall"})

    if schema_paywall or meta_paywall:
        status = "confirmed"
    elif len(all_found) >= 2:
        status = "likely"
    elif all_found:
        status = "possible"
    else:
        status = "no"

    return {
        "paywall": status,
        "paywall_signals_sr": found_sr,
        "paywall_signals_en": found_en,
        "paywall_schema": schema_paywall,
    }


def check_bot_protection(response, elapsed):
    headers = dict(response.headers)
    text_sample = response.text[:3000].lower()

    cf = bool(headers.get("CF-RAY") or "cloudflare" in headers.get("Server", "").lower())
    captcha = any(x in text_sample for x in ["captcha", "recaptcha", "hcaptcha", "turnstile"])
    rate_limited = response.status_code == 429
    blocked = response.status_code == 403
    akamai = "akamaighost" in headers.get("Server", "").lower()

    challenge = any(x in text_sample for x in [
        "checking your browser", "please wait", "verifying you are human",
        "ddos-guard", "ddosg"
    ])

    protection_level = "none"
    if captcha or challenge:
        protection_level = "high"
    elif cf or akamai or rate_limited:
        protection_level = "medium"
    elif blocked:
        protection_level = "low_403"

    return {
        "status_code": response.status_code,
        "response_time_ms": int(elapsed * 1000),
        "final_url": str(response.url),
        "cloudflare": cf,
        "akamai": akamai,
        "captcha_detected": captcha,
        "challenge_page": challenge,
        "rate_limited": rate_limited,
        "access_blocked": blocked,
        "bot_protection_level": protection_level,
        "server_header": headers.get("Server", ""),
        "x_powered_by": headers.get("X-Powered-By", ""),
        "content_encoding": headers.get("Content-Encoding", ""),
        "page_size_kb": round(len(response.content) / 1024, 1),
    }


def check_article_structure(soup, base_url):
    result = {
        "article_links_found": 0,
        "article_url_pattern": None,
        "article_url_samples": [],
        "has_pagination": False,
        "pagination_type": None,
        "pagination_url_pattern": None,
        "listing_selectors_found": [],
        "has_author_visible": False,
        "has_date_visible": False,
        "has_category_visible": False,
    }

    links = soup.find_all("a", href=True)
    article_links = set()
    base_domain = urlparse(base_url).netloc

    for link in links:
        href = link.get("href", "")
        if not href or href.startswith("#") or href in ["/", ""]:
            continue
        full_url = urljoin(base_url, href)
        parsed = urlparse(full_url)
        if parsed.netloc != base_domain:
            continue
        path_parts = [p for p in parsed.path.strip("/").split("/") if p]
        if len(path_parts) >= 2 and len(parsed.path) > 15:
            # Filtriraj staticne stranice
            if not any(x in parsed.path for x in ["/tag/", "/autor/", "/author/", "/category/", "/search/"]):
                article_links.add(full_url)

    result["article_links_found"] = len(article_links)

    samples = list(article_links)[:5]
    result["article_url_samples"] = samples

    if samples:
        paths = [urlparse(s).path for s in samples]
        # Pokusaj da otkrijes pattern
        common_parts = paths[0].strip("/").split("/")
        if common_parts:
            result["article_url_pattern"] = "/" + common_parts[0] + "/SLUG"
            # Ako path ima format /kategorija/slug
            if len(common_parts) >= 2:
                result["article_url_pattern"] = "/" + common_parts[0] + "/SLUG"

    # Paginacija
    next_links = [
        soup.find("a", string=re.compile(r"sledec|next|>>|›|»|dalje", re.I)),
        soup.find("a", class_=re.compile(r"next|pagination__next", re.I)),
        soup.find(class_=re.compile(r"pagination|pager|load-more", re.I)),
    ]
    load_more = soup.find("button", string=re.compile(r"ucitaj|load more|vise vesti|prikazi vise", re.I))

    if any(next_links):
        result["has_pagination"] = True
        result["pagination_type"] = "next_page_link"
        # Pokusaj da nadje URL pattern paginacije
        for nl in next_links:
            if nl and nl.get("href"):
                result["pagination_url_pattern"] = nl["href"]
                break
    elif load_more:
        result["has_pagination"] = True
        result["pagination_type"] = "load_more_button"

    # Listing selektori
    for selector in ["article", ".article", ".post", ".news-item", ".story",
                     ".item", "[class*='article']", "[class*='news']", ".card"]:
        try:
            elements = soup.select(selector)
            if len(elements) >= 3:
                result["listing_selectors_found"].append(f"{selector}:{len(elements)}")
        except Exception:
            pass

    # Meta informacije vidljive na listingu
    result["has_author_visible"] = bool(
        soup.find(class_=re.compile(r"author|autor", re.I)) or
        soup.find(attrs={"itemprop": "author"})
    )
    result["has_date_visible"] = bool(
        soup.find("time") or
        soup.find(class_=re.compile(r"date|datum|time|vreme", re.I))
    )
    result["has_category_visible"] = bool(
        soup.find(class_=re.compile(r"categor|rubrika|tag", re.I))
    )

    return result


def check_live_blog(soup, response_text):
    signals = []
    text_lower = response_text.lower()

    for kw in ["liveblog", "live-blog", "live blog", "uzivo", "u zivo",
                "LiveBlogPosting", "live prenos", "pratite uzivo"]:
        if kw.lower() in text_lower:
            signals.append(kw)

    schema_live = "LiveBlogPosting" in response_text

    return {
        "has_live_blog_format": bool(signals),
        "live_blog_schema": schema_live,
        "live_blog_signals": signals[:5],
    }


def check_cyrillic(response_text):
    sample = response_text[2000:8000]  # Skip header/nav deo
    cyrillic = len(re.findall(r'[\u0400-\u04FF]', sample))
    latin_sr = len(re.findall(r'[a-zšđčćž]', sample, re.I))

    if cyrillic > latin_sr * 2:
        default = "yes"
    elif cyrillic > 50:
        default = "mixed"
    else:
        default = "no"

    return {
        "cyrillic_default": default,
        "cyrillic_char_count": cyrillic,
        "latin_char_count": latin_sr,
    }


def check_additional_meta(soup):
    """Proveri dodatne meta tagove korisne za scraping."""
    result = {
        "has_canonical": False,
        "has_og_title": False,
        "has_og_description": False,
        "has_og_image": False,
        "has_og_type": False,
        "og_type_value": None,
        "has_schema_org": False,
        "schema_types": [],
        "has_amp": False,
        "language_declared": None,
    }

    if soup.find("link", rel="canonical"):
        result["has_canonical"] = True

    for prop in ["og:title", "og:description", "og:image", "og:type"]:
        meta = soup.find("meta", property=prop)
        if meta:
            key = prop.replace(":", "_").replace("og_", "has_og_")
            result[f"has_{prop.replace(':', '_')}"] = True
            if prop == "og:type":
                result["og_type_value"] = meta.get("content", "")

    html_str = str(soup)
    if "@type" in html_str:
        result["has_schema_org"] = True
        types = re.findall(r'"@type"\s*:\s*"([^"]+)"', html_str)
        result["schema_types"] = list(set(types))[:10]

    if soup.find("link", rel="amphtml") or soup.find("html", attrs={"amp": True}):
        result["has_amp"] = True

    html_tag = soup.find("html")
    if html_tag:
        result["language_declared"] = html_tag.get("lang")

    return result


# ── Analiza strukture clanka ───────────────────────────────────────────────────

def check_article_page(article_url, site_name):
    """
    Fetchuj konkretan clanak i analiziraj tacnu strukturu podataka.
    Ovo je kljucno za scraper implementaciju - otkriva stvarne CSS selektore.
    """
    result = {
        "article_url_tested": article_url,
        "article_fetch_status": None,
        "article_fetch_error": None,

        # Naslov
        "title_in_h1": False,
        "title_h1_selector": None,
        "title_og_tag": False,

        # Podnaslov
        "has_subtitle": False,
        "subtitle_selector": None,

        # Tekst clanka
        "text_selector": None,
        "text_word_count": 0,
        "text_in_single_element": False,
        "text_element_tag": None,

        # Autor
        "has_author": False,
        "author_selector": None,
        "author_value_sample": None,
        "author_is_linked": False,

        # Timestamp
        "timestamp_in_article": False,
        "timestamp_selector": None,
        "timestamp_value_sample": None,
        "timestamp_format_sample": None,
        "updated_timestamp": False,
        "updated_timestamp_selector": None,

        # Kategorija / rubrika
        "has_category": False,
        "category_selector": None,
        "category_value_sample": None,

        # Tagovi
        "has_tags": False,
        "tags_selector": None,
        "tags_count_sample": 0,
        "tags_sample": [],

        # Slika
        "has_main_image": False,
        "main_image_selector": None,
        "has_image_caption": False,

        # Komentari
        "has_comment_count": False,
        "comment_count_selector": None,
        "comment_count_sample": None,

        # Relacioni clanci
        "has_related_articles": False,
        "related_articles_selector": None,

        # Schema.org
        "article_schema_type": None,
        "schema_fields_available": [],

        # Ukupna procena
        "available_fields": [],
        "missing_fields": [],
        "scraper_notes": [],
    }

    r, err = fetch(article_url, label=f"{site_name} article")
    if err:
        result["article_fetch_error"] = err["error_message"]
        result["article_fetch_error_type"] = err["error_type"]
        log.warning(f"[{site_name}] Article fetch greska [{err['error_type']}]: {article_url}")
        return result

    result["article_fetch_status"] = r.status_code
    if r.status_code != 200:
        log.warning(f"[{site_name}] Article HTTP {r.status_code}: {article_url}")
        return result

    try:
        soup = BeautifulSoup(r.content, "lxml")
    except Exception as e:
        result["article_fetch_error"] = f"Parse greska: {e}"
        return result

    html_str = str(soup)

    # ── Naslov ────────────────────────────────────────────────────────────
    h1 = soup.find("h1")
    if h1 and len(h1.get_text(strip=True)) > 10:
        result["title_in_h1"] = True
        classes = h1.get("class", [])
        result["title_h1_selector"] = f"h1.{'.'.join(classes)}" if classes else "h1"
        result["available_fields"].append("title")
    elif soup.find("meta", property="og:title"):
        result["title_og_tag"] = True
        result["available_fields"].append("title_og_only")
        result["scraper_notes"].append("Naslov samo u OG tagu - moguc JS rendering")
    else:
        result["missing_fields"].append("title")

    # ── Podnaslov ─────────────────────────────────────────────────────────
    for selector in ["h2.subtitle", ".subtitle", ".lead", ".podtekst",
                     ".intro", "[class*='subtitle']", "[class*='lead']", "h2.article"]:
        try:
            el = soup.select_one(selector)
            if el and len(el.get_text(strip=True)) > 10:
                result["has_subtitle"] = True
                result["subtitle_selector"] = selector
                result["available_fields"].append("subtitle")
                break
        except Exception:
            pass

    # ── Tekst clanka ──────────────────────────────────────────────────────
    text_candidates = [
        ("article .content", soup.select_one("article .content")),
        ("article", soup.find("article")),
        (".article-body", soup.select_one(".article-body")),
        (".article-content", soup.select_one(".article-content")),
        (".post-content", soup.select_one(".post-content")),
        (".entry-content", soup.select_one(".entry-content")),
        ("[class*='article-text']", soup.select_one("[class*='article-text']")),
        ("[class*='article-body']", soup.select_one("[class*='article-body']")),
        ("[class*='content']", soup.select_one("[class*='content']")),
        (".text", soup.select_one(".text")),
        ("main", soup.find("main")),
    ]

    best_text = None
    best_selector = None
    best_word_count = 0

    for selector, el in text_candidates:
        if not el:
            continue
        # Ukloni navigaciju, ads, related articles pre brojanja
        for noise in el.find_all(["nav", "aside", "script", "style",
                                   "iframe", "figure"]):
            noise.decompose()
        text = el.get_text(separator=" ", strip=True)
        word_count = len(text.split())
        if word_count > best_word_count and word_count > 50:
            best_word_count = word_count
            best_text = el
            best_selector = selector

    if best_text:
        result["text_selector"] = best_selector
        result["text_word_count"] = best_word_count
        result["text_in_single_element"] = True
        result["text_element_tag"] = best_text.name
        result["available_fields"].append("text")
        if best_word_count < 100:
            result["scraper_notes"].append(f"Tekst kratak ({best_word_count} reci) - moguc JS rendering ili paywall")
    else:
        result["missing_fields"].append("text")
        result["scraper_notes"].append("Tekst clanka nije pronadjen - verovatno JS rendering")

    # ── Autor ─────────────────────────────────────────────────────────────
    author_candidates = [
        "[class*='author']", "[class*='autor']", "[rel='author']",
        "[itemprop='author']", ".byline", ".by-author",
        "a[href*='/autor/']", "a[href*='/author/']",
        "span.author", "div.author",
    ]
    for selector in author_candidates:
        try:
            el = soup.select_one(selector)
            if el:
                text = el.get_text(strip=True)
                if 2 < len(text) < 80:
                    result["has_author"] = True
                    result["author_selector"] = selector
                    result["author_value_sample"] = text[:50]
                    result["author_is_linked"] = el.name == "a" or bool(el.find("a"))
                    result["available_fields"].append("author")
                    break
        except Exception:
            pass

    if not result["has_author"]:
        # Pokusaj schema.org
        author_schema = re.search(r'"author"\s*:\s*\{[^}]*"name"\s*:\s*"([^"]+)"', html_str)
        if author_schema:
            result["has_author"] = True
            result["author_selector"] = "schema.org JSON-LD"
            result["author_value_sample"] = author_schema.group(1)
            result["available_fields"].append("author_schema")
        else:
            result["missing_fields"].append("author")

    # ── Timestamp ─────────────────────────────────────────────────────────
    time_candidates = [
        ("time[datetime]", lambda el: el.get("datetime")),
        ("time[pubdate]", lambda el: el.get("datetime") or el.get_text(strip=True)),
        ("[class*='date']", lambda el: el.get_text(strip=True)),
        ("[class*='time']", lambda el: el.get_text(strip=True)),
        ("[class*='datum']", lambda el: el.get_text(strip=True)),
        ("[itemprop='datePublished']", lambda el: el.get("content") or el.get_text(strip=True)),
        ("meta[property='article:published_time']", lambda el: el.get("content")),
    ]

    for selector, getter in time_candidates:
        try:
            el = soup.select_one(selector)
            if el:
                val = getter(el)
                if val and len(str(val)) > 4:
                    result["timestamp_in_article"] = True
                    result["timestamp_selector"] = selector
                    result["timestamp_value_sample"] = str(val)[:50]
                    # Detektuj format
                    if re.search(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}', str(val)):
                        result["timestamp_format_sample"] = "ISO8601"
                    elif re.search(r'\d{1,2}\.\s*\w+\s*\d{4}', str(val)):
                        result["timestamp_format_sample"] = "SR_DATE (DD. mesec YYYY)"
                    else:
                        result["timestamp_format_sample"] = "other"
                    result["available_fields"].append("published_at")
                    break
        except Exception:
            pass

    # Provjeri updated timestamp
    for selector in ["[itemprop='dateModified']", "meta[property='og:updated_time']",
                     "[class*='updated']", "[class*='modified']"]:
        try:
            el = soup.select_one(selector)
            if el:
                result["updated_timestamp"] = True
                result["updated_timestamp_selector"] = selector
                result["available_fields"].append("updated_at")
                break
        except Exception:
            pass

    if not result["timestamp_in_article"]:
        result["missing_fields"].append("published_at")
        result["scraper_notes"].append("Timestamp nije pronadjen u HTML-u - koristiti OG meta tag")

    # ── Kategorija ────────────────────────────────────────────────────────
    cat_candidates = [
        "[class*='categor']", "[class*='rubrika']", "[class*='section']",
        "[itemprop='articleSection']", "a[href*='/category/']",
        "a[href*='/rubrika/']", "a[href*='/kategorija/']",
        ".breadcrumb a:last-child", "nav.breadcrumb",
    ]
    for selector in cat_candidates:
        try:
            el = soup.select_one(selector)
            if el:
                text = el.get_text(strip=True)
                if 2 < len(text) < 60:
                    result["has_category"] = True
                    result["category_selector"] = selector
                    result["category_value_sample"] = text
                    result["available_fields"].append("category")
                    break
        except Exception:
            pass

    if not result["has_category"]:
        result["missing_fields"].append("category")

    # ── Tagovi ────────────────────────────────────────────────────────────
    tag_candidates = [
        "[class*='tag']", "[class*='label']", "[rel='tag']",
        "a[href*='/tag/']", "a[href*='/tags/']",
        "[class*='keyword']",
    ]
    for selector in tag_candidates:
        try:
            els = soup.select(selector)
            if len(els) >= 2:
                tags = [el.get_text(strip=True) for el in els if 1 < len(el.get_text(strip=True)) < 40]
                if len(tags) >= 2:
                    result["has_tags"] = True
                    result["tags_selector"] = selector
                    result["tags_count_sample"] = len(tags)
                    result["tags_sample"] = tags[:5]
                    result["available_fields"].append("tags")
                    break
        except Exception:
            pass

    if not result["has_tags"]:
        result["missing_fields"].append("tags")

    # ── Glavna slika ──────────────────────────────────────────────────────
    img_candidates = [
        "article img", ".article-image img", ".main-image img",
        "figure img", "[class*='hero'] img", "[class*='featured'] img",
        ".post-thumbnail img",
    ]
    for selector in img_candidates:
        try:
            el = soup.select_one(selector)
            if el and (el.get("src") or el.get("data-src")):
                result["has_main_image"] = True
                result["main_image_selector"] = selector
                result["available_fields"].append("image_url")
                # Caption
                fig = el.find_parent("figure")
                if fig and fig.find("figcaption"):
                    result["has_image_caption"] = True
                    result["available_fields"].append("image_caption")
                break
        except Exception:
            pass

    # ── Broj komentara ────────────────────────────────────────────────────
    comment_candidates = [
        "[class*='comment-count']", "[class*='comments-count']",
        "a[href*='#comment']", "[class*='komentara']",
        "[class*='comment'] span", ".disqus-comment-count",
    ]
    for selector in comment_candidates:
        try:
            el = soup.select_one(selector)
            if el:
                text = el.get_text(strip=True)
                if re.search(r'\d', text):
                    result["has_comment_count"] = True
                    result["comment_count_selector"] = selector
                    result["comment_count_sample"] = text[:20]
                    result["available_fields"].append("comment_count")
                    break
        except Exception:
            pass

    # ── Related articles ──────────────────────────────────────────────────
    related_candidates = [
        "[class*='related']", "[class*='slicno']", "[class*='preporucujemo']",
        "[class*='recommended']", "[class*='more-articles']",
    ]
    for selector in related_candidates:
        try:
            el = soup.select_one(selector)
            if el and len(el.find_all("a")) >= 2:
                result["has_related_articles"] = True
                result["related_articles_selector"] = selector
                result["scraper_notes"].append(f"Related articles u {selector} - iskljuciti iz text scraping-a")
                break
        except Exception:
            pass

    # ── Schema.org analiza ────────────────────────────────────────────────
    schema_matches = re.findall(r'"@type"\s*:\s*"([^"]+)"', html_str)
    if schema_matches:
        result["article_schema_type"] = schema_matches[0] if schema_matches else None

        # Koja polja postoje u schema
        schema_fields = []
        for field in ["headline", "author", "datePublished", "dateModified",
                       "description", "image", "articleBody", "keywords",
                       "articleSection", "publisher", "url"]:
            if f'"{field}"' in html_str:
                schema_fields.append(field)
        result["schema_fields_available"] = schema_fields
        if schema_fields:
            result["scraper_notes"].append(f"Schema.org polja dostupna: {', '.join(schema_fields)}")

    # ── Finalna lista dostupnih polja ─────────────────────────────────────
    log.info(f"[{site_name}] Article analiza zavrsena:")
    log.info(f"[{site_name}]   Dostupna polja: {result['available_fields']}")
    log.info(f"[{site_name}]   Nedostaju: {result['missing_fields']}")
    log.info(f"[{site_name}]   Napomene: {result['scraper_notes']}")

    return result


# ── Strategija i tezina ────────────────────────────────────────────────────────

def derive_strategy(r):
    parts = []
    if r.get("wp_api_available"):
        parts.append("WordPress REST API (/wp-json/wp/v2/posts)")
    elif r.get("rss_status") == "confirmed":
        parts.append(f"RSS ({r.get('rss_url', '')})")
    else:
        parts.append("HTML listing scraping")

    js_risk = r.get("js_rendering_risk", "low")
    if js_risk == "high":
        parts.append("POTREBAN PLAYWRIGHT")
    elif js_risk == "medium":
        parts.append("proveriti potrebu za Playwright")

    if r.get("og_published_time"):
        parts.append("og:published/updated_time za timestamp")
    elif r.get("schema_date_published"):
        parts.append("schema datePublished za timestamp")
    elif r.get("time_element"):
        parts.append("<time> element za timestamp")

    if r.get("cyrillic_default") == "yes":
        parts.append("normalizovati cirilicu")

    if r.get("paywall") in ["confirmed", "likely"]:
        parts.append("paywall - biljeziti i skipovati")

    if r.get("cloudflare"):
        parts.append("Cloudflare - oprezno sa frecencijom")

    return " | ".join(parts) if parts else "Rucna inspekcija potrebna"


def derive_difficulty(r):
    score = 0
    reasons = []

    if r.get("main_page_status", 0) not in [200, 301, 302] and r.get("main_page_status", 0) != 0:
        score += 3
        reasons.append("sajt nedostupan")
    if r.get("js_rendering_risk") == "high":
        score += 3
        reasons.append("JS rendering")
    elif r.get("js_rendering_risk") == "medium":
        score += 1
        reasons.append("moguc JS rendering")
    if r.get("cloudflare"):
        score += 1
        reasons.append("Cloudflare")
    if r.get("captcha_detected") or r.get("challenge_page"):
        score += 3
        reasons.append("captcha/challenge")
    if r.get("access_blocked"):
        score += 2
        reasons.append("403 blokiran")
    if r.get("wp_api_available"):
        score -= 2
        reasons.append("-WP API")
    if r.get("rss_status") == "confirmed":
        score -= 1
        reasons.append("-RSS")
    if r.get("og_published_time"):
        score -= 1
        reasons.append("-OG timestamps")

    if score <= 0:
        return "easy", reasons
    elif score <= 3:
        return "medium", reasons
    return "hard", reasons


# ── Glavna analiza sajta ───────────────────────────────────────────────────────

def analyze_site(site):
    log.info(f"\n{'='*60}")
    log.info(f"[{site['name']}] Pocinje analiza: {site['url']}")
    log.info(f"{'='*60}")

    result = {
        "id": site["id"],
        "name": site["name"],
        "url": site["url"],
        "listing_url_used": site["listing"],
        "analyzed_at": datetime.now().isoformat(),
        "main_page_error": None,
        "main_page_error_type": None,
        "listing_error": None,
        "listing_error_type": None,
        "partial_analysis": False,
    }

    # ── 1. Glavna stranica ─────────────────────────────────────────────────
    log.info(f"[{site['name']}] [1/7] Fetchujem glavnu stranicu...")
    r, err = fetch(site["url"], label=site["name"])

    if err:
        result["main_page_error"] = err["error_message"]
        result["main_page_error_type"] = err["error_type"]
        result["main_page_status"] = 0
        log.error(f"[{site['name']}] Glavna stranica nedostupna [{err['error_type']}] - preskacemo detalje")

        # RSS i dalje mozemo proveriti
        log.info(f"[{site['name']}] [2/7] Provjeravam RSS uprkos gresci na glavnoj...")
        rss = check_rss(site["rss_candidates"], site["name"])
        result.update(rss)
        result["partial_analysis"] = True
        result["scraping_difficulty"] = "hard"
        result["scraping_difficulty_reasons"] = ["sajt nedostupan"]
        result["scraping_strategy"] = "SAJT NEDOSTUPAN - potrebna rucna provjera"
        return result

    start_time = time.time()

    try:
        soup = BeautifulSoup(r.content, "lxml")
    except Exception as e:
        log.error(f"[{site['name']}] HTML parse greska: {e}")
        result["main_page_error"] = f"HTML parse greska: {e}"
        result["main_page_error_type"] = "HTML_PARSE_ERROR"
        result["partial_analysis"] = True

    elapsed = time.time() - start_time
    result["main_page_status"] = r.status_code

    bot = check_bot_protection(r, elapsed)
    result.update(bot)
    log.info(f"[{site['name']}] Status: {r.status_code}, Vreme: {bot['response_time_ms']}ms, CF: {bot['cloudflare']}, Blokiran: {bot['access_blocked']}")

    # ── 2. RSS ─────────────────────────────────────────────────────────────
    log.info(f"[{site['name']}] [2/7] Provjeravam RSS...")
    rss = check_rss(site["rss_candidates"], site["name"])
    result.update(rss)

    # ── 3. WordPress ───────────────────────────────────────────────────────
    log.info(f"[{site['name']}] [3/7] Provjeravam WordPress...")
    try:
        wp = check_wordpress(site["url"], soup)
        result.update(wp)
        log.info(f"[{site['name']}] WP: {wp['is_wordpress']}, ver: {wp['wordpress_version']}, API: {wp['wp_api_available']}")
    except Exception as e:
        log.warning(f"[{site['name']}] WordPress check greska: {e}")
        result["wp_check_error"] = str(e)

    # ── 4. JS rendering ────────────────────────────────────────────────────
    log.info(f"[{site['name']}] [4/7] Analiziram JS rendering...")
    try:
        js = check_js_rendering(soup, r.text)
        result.update(js)
        log.info(f"[{site['name']}] JS rizik: {js['js_rendering_risk']}, signali: {js['js_signals']}")
    except Exception as e:
        log.warning(f"[{site['name']}] JS check greska: {e}")

    # ── 5. Meta tagovi ─────────────────────────────────────────────────────
    log.info(f"[{site['name']}] [5/7] Provjeravam meta tagove i timestamps...")
    try:
        ts = check_timestamps(soup)
        result.update(ts)
        meta = check_additional_meta(soup)
        result.update(meta)
        log.info(f"[{site['name']}] OG published: {ts['og_published_time']}, reliability: {ts['timestamp_reliability']}")
    except Exception as e:
        log.warning(f"[{site['name']}] Meta check greska: {e}")

    # ── 6. Listing stranica ────────────────────────────────────────────────
    log.info(f"[{site['name']}] [6/7] Analiziram listing stranicu: {site['listing']}...")
    rl, err_l = fetch(site["listing"], label=f"{site['name']} listing")

    if err_l:
        result["listing_error"] = err_l["error_message"]
        result["listing_error_type"] = err_l["error_type"]
        result["partial_analysis"] = True
        log.warning(f"[{site['name']}] Listing nedostupan [{err_l['error_type']}] - preskacemo strukturu")
    else:
        result["listing_status"] = rl.status_code
        try:
            soup_l = BeautifulSoup(rl.content, "lxml")

            struct = check_article_structure(soup_l, site["url"])
            result.update(struct)

            paywall = check_paywall(soup_l, rl.text)
            result.update(paywall)

            live = check_live_blog(soup_l, rl.text)
            result.update(live)

            cyr = check_cyrillic(rl.text)
            result.update(cyr)

            log.info(f"[{site['name']}] Clanci: {struct['article_links_found']}, Paginacija: {struct['has_pagination']} ({struct['pagination_type']})")
            log.info(f"[{site['name']}] Paywall: {paywall['paywall']}, Live blog: {live['has_live_blog_format']}, Cirilica: {cyr['cyrillic_default']}")

        except Exception as e:
            log.warning(f"[{site['name']}] Listing parse greska: {e}\n{traceback.format_exc()}")
            result["listing_parse_error"] = str(e)
            result["partial_analysis"] = True

    # ── 7. Analiza konkretnog clanka ───────────────────────────────────────
    log.info(f"[{site['name']}] [7/8] Analiziram strukturu konkretnog clanka...")
    article_url = None

    # Pokusaj da nadjemo URL clanka iz listing stranice
    if not result.get("listing_error") and result.get("article_url_samples"):
        article_url = result["article_url_samples"][0]
    # Ili iz RSS feeda
    elif result.get("rss_status") == "confirmed" and result.get("rss_url"):
        try:
            feed = feedparser.parse(result["rss_url"])
            if feed.entries:
                article_url = feed.entries[0].get("link")
        except Exception as e:
            log.warning(f"[{site['name']}] RSS fetch za article URL greska: {e}")

    if article_url:
        log.info(f"[{site['name']}] Testiram clanak: {article_url}")
        try:
            article = check_article_page(article_url, site["name"])
            result["article_analysis"] = article
            # Flatten kljucna polja za CSV
            result["art_available_fields"] = " | ".join(article.get("available_fields", []))
            result["art_missing_fields"] = " | ".join(article.get("missing_fields", []))
            result["art_text_selector"] = article.get("text_selector")
            result["art_text_word_count"] = article.get("text_word_count")
            result["art_title_in_h1"] = article.get("title_in_h1")
            result["art_has_author"] = article.get("has_author")
            result["art_author_selector"] = article.get("author_selector")
            result["art_timestamp_selector"] = article.get("timestamp_selector")
            result["art_timestamp_format"] = article.get("timestamp_format_sample")
            result["art_has_category"] = article.get("has_category")
            result["art_category_selector"] = article.get("category_selector")
            result["art_has_tags"] = article.get("has_tags")
            result["art_tags_selector"] = article.get("tags_selector")
            result["art_has_image"] = article.get("has_main_image")
            result["art_schema_type"] = article.get("article_schema_type")
            result["art_schema_fields"] = " | ".join(article.get("schema_fields_available", []))
            result["art_scraper_notes"] = " | ".join(article.get("scraper_notes", []))
        except Exception as e:
            log.warning(f"[{site['name']}] Article analiza greska: {e}\n{traceback.format_exc()}")
            result["article_analysis_error"] = str(e)
    else:
        log.warning(f"[{site['name']}] Nije pronadjen URL clanka za analizu - preskacemo")
        result["article_analysis_error"] = "Nije pronadjen URL clanka"

    # ── 8. Finalna procena ─────────────────────────────────────────────────
    log.info(f"[{site['name']}] [8/8] Izvodim strategiju i tezinu...")
    diff, reasons = derive_difficulty(result)
    result["scraping_difficulty"] = diff
    result["scraping_difficulty_reasons"] = reasons
    result["scraping_strategy"] = derive_strategy(result)

    log.info(f"[{site['name']}] Tezina: {diff} ({', '.join(reasons)})")
    log.info(f"[{site['name']}] Strategija: {result['scraping_strategy']}")
    log.info(f"[{site['name']}] Analiza zavrsena")

    return result


# ── Save i summary ─────────────────────────────────────────────────────────────

def save_results(results):
    json_path = f"mediascope_analiza_{TIMESTAMP}.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2, default=str)
    log.info(f"JSON sacuvan: {json_path}")

    csv_fields = [
        "name", "url", "analyzed_at",
        "main_page_status", "response_time_ms", "page_size_kb",
        "cloudflare", "akamai", "captcha_detected", "challenge_page",
        "access_blocked", "bot_protection_level", "server_header",
        "rss_status", "rss_url", "rss_entries_count", "rss_has_dates",
        "rss_has_content", "rss_sample_title", "rss_error_type",
        "is_wordpress", "wordpress_version", "wp_api_available", "wp_api_url",
        "wp_api_error_type", "wp_detection_signals",
        "js_rendering_risk", "has_next_js", "has_react_root", "has_nuxt",
        "has_angular", "has_vue", "content_in_html", "js_signals",
        "og_published_time", "og_updated_time", "timestamp_reliability",
        "sample_timestamp", "timestamp_format", "schema_date_published",
        "has_schema_org", "schema_types", "og_type_value", "has_amp",
        "language_declared",
        "paywall", "paywall_schema",
        "has_live_blog_format", "live_blog_schema",
        "cyrillic_default", "cyrillic_char_count",
        "article_links_found", "article_url_pattern", "article_url_samples",
        "has_pagination", "pagination_type", "pagination_url_pattern",
        "listing_selectors_found", "has_author_visible", "has_date_visible",
        "scraping_difficulty", "scraping_difficulty_reasons", "scraping_strategy",
        "partial_analysis", "main_page_error_type", "listing_error_type",
        # Article analiza
        "art_available_fields", "art_missing_fields",
        "art_title_in_h1", "art_text_selector", "art_text_word_count",
        "art_has_author", "art_author_selector",
        "art_timestamp_selector", "art_timestamp_format",
        "art_has_category", "art_category_selector",
        "art_has_tags", "art_tags_selector",
        "art_has_image", "art_schema_type", "art_schema_fields",
        "art_scraper_notes", "article_analysis_error",
    ]

    csv_path = f"mediascope_analiza_{TIMESTAMP}.csv"
    with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=csv_fields, extrasaction="ignore")
        writer.writeheader()
        for r in results:
            row = {}
            for k in csv_fields:
                val = r.get(k, "")
                if isinstance(val, list):
                    val = " | ".join(str(x) for x in val)
                elif isinstance(val, bool):
                    val = "DA" if val else "ne"
                row[k] = val
            writer.writerow(row)

    log.info(f"CSV sacuvan: {csv_path}")
    return csv_path, json_path


def print_summary(results):
    log.info("\n" + "="*60)
    log.info("FINALNI SUMMARY")
    log.info("="*60)

    total = len(results)
    rss_ok = sum(1 for r in results if r.get("rss_status") == "confirmed")
    wp = sum(1 for r in results if r.get("is_wordpress"))
    wp_api = sum(1 for r in results if r.get("wp_api_available"))
    js_high = sum(1 for r in results if r.get("js_rendering_risk") == "high")
    js_med = sum(1 for r in results if r.get("js_rendering_risk") == "medium")
    cf = sum(1 for r in results if r.get("cloudflare"))
    blocked = sum(1 for r in results if r.get("access_blocked"))
    easy = sum(1 for r in results if r.get("scraping_difficulty") == "easy")
    hard = sum(1 for r in results if r.get("scraping_difficulty") == "hard")
    partial = sum(1 for r in results if r.get("partial_analysis"))
    errors_main = sum(1 for r in results if r.get("main_page_error_type"))
    errors_listing = sum(1 for r in results if r.get("listing_error_type"))

    log.info(f"\nUkupno: {total} | Greske glavna str.: {errors_main} | Greske listing: {errors_listing} | Parcijalna analiza: {partial}")
    log.info(f"RSS potvrdjen: {rss_ok}/{total}")
    log.info(f"WordPress: {wp}/{total} (API dostupan: {wp_api})")
    log.info(f"JS rizik - visok: {js_high} | srednji: {js_med}")
    log.info(f"Cloudflare: {cf}/{total} | Blokirano (403): {blocked}/{total}")
    log.info(f"Tezina - easy: {easy} | medium: {total-easy-hard} | hard: {hard}")

    log.info(f"\n{'Sajt':<16} {'St':<5} {'ms':<6} {'RSS':<11} {'WP':<4} {'JS':<8} {'CF':<4} {'Tezina'}")
    log.info("-"*70)
    for r in results:
        name = r.get("name", "")[:15]
        st = str(r.get("main_page_status", "ERR"))
        ms = str(r.get("response_time_ms", "?"))
        rss = r.get("rss_status", "?")[:10]
        wp_f = "DA" if r.get("is_wordpress") else "ne"
        js = r.get("js_rendering_risk", "?")[:7]
        cf_f = "DA" if r.get("cloudflare") else "-"
        diff = r.get("scraping_difficulty", "?")
        partial_f = " (!)" if r.get("partial_analysis") else ""
        log.info(f"{name:<16} {st:<5} {ms:<6} {rss:<11} {wp_f:<4} {js:<8} {cf_f:<4} {diff}{partial_f}")


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    log.info("MediaScope - Tehnicka analiza srpskih medijskih sajtova")
    log.info(f"Pocetak: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    log.info(f"Log fajl: {LOG_PATH}")
    log.info(f"Analiziram {len(SITES)} sajtova...\n")

    results = []

    for i, site in enumerate(SITES):
        log.info(f"\n[{i+1}/{len(SITES)}] Pocinje: {site['name']}")

        try:
            result = analyze_site(site)
        except Exception as e:
            log.error(f"KRITICNA GRESKA za {site['name']}: {e}\n{traceback.format_exc()}")
            result = {
                "id": site["id"],
                "name": site["name"],
                "url": site["url"],
                "analyzed_at": datetime.now().isoformat(),
                "main_page_error": str(e),
                "main_page_error_type": classify_error(e),
                "partial_analysis": True,
                "scraping_difficulty": "hard",
                "scraping_strategy": f"KRITICNA GRESKA: {e}",
            }

        results.append(result)

        if i < len(SITES) - 1:
            log.debug(f"Cekam {INTER_SITE_DELAY}s pre sledeceg sajta...")
            time.sleep(INTER_SITE_DELAY)

    print_summary(results)
    csv_path, json_path = save_results(results)

    log.info(f"\nGotovo! {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    log.info(f"CSV: {csv_path}")
    log.info(f"JSON: {json_path}")
    log.info(f"Log: {LOG_PATH}")


if __name__ == "__main__":
    main()
