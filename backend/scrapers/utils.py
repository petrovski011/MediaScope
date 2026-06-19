from __future__ import annotations

import json
import re
from datetime import datetime
from typing import Optional

from bs4 import BeautifulSoup, Tag

# Full Serbian Cyrillic → Latin transliteration map
_CYR: dict[str, str] = {
    "А": "A",  "Б": "B",  "В": "V",  "Г": "G",  "Д": "D",  "Ђ": "Đ",
    "Е": "E",  "Ж": "Ž",  "З": "Z",  "И": "I",  "Ј": "J",  "К": "K",
    "Л": "L",  "Љ": "Lj", "М": "M",  "Н": "N",  "Њ": "Nj", "О": "O",
    "П": "P",  "Р": "R",  "С": "S",  "Т": "T",  "Ћ": "Ć",  "У": "U",
    "Ф": "F",  "Х": "H",  "Ц": "C",  "Ч": "Č",  "Џ": "Dž", "Ш": "Š",
    "а": "a",  "б": "b",  "в": "v",  "г": "g",  "д": "d",  "ђ": "đ",
    "е": "e",  "ж": "ž",  "з": "z",  "и": "i",  "ј": "j",  "к": "k",
    "л": "l",  "љ": "lj", "м": "m",  "н": "n",  "њ": "nj", "о": "o",
    "п": "p",  "р": "r",  "с": "s",  "т": "t",  "ћ": "ć",  "у": "u",
    "ф": "f",  "х": "h",  "ц": "c",  "ч": "č",  "џ": "dž", "ш": "š",
}

# Month name → number — Latin + Cyrillic, all inflections
_MONTHS: dict[str, int] = {
    "januar": 1,    "januara": 1,
    "februar": 2,   "februara": 2,
    "mart": 3,      "marta": 3,
    "april": 4,     "aprila": 4,
    "maj": 5,       "maja": 5,
    "jun": 6,       "juna": 6,    "juni": 6,
    "jul": 7,       "jula": 7,    "juli": 7,
    "avgust": 8,    "avgusta": 8,
    "septembar": 9, "septembra": 9,
    "oktobar": 10,  "oktobra": 10,
    "novembar": 11, "novembra": 11,
    "decembar": 12, "decembra": 12,
    # Cyrillic
    "јануар": 1,   "јануара": 1,
    "фебруар": 2,  "фебруара": 2,
    "март": 3,     "марта": 3,
    "април": 4,    "априла": 4,
    "мај": 5,      "маја": 5,
    "јун": 6,      "јуна": 6,    "јуни": 6,
    "јул": 7,      "јула": 7,    "јули": 7,
    "август": 8,   "августа": 8,
    "септембар": 9,  "септембра": 9,
    "октобар": 10,   "октобра": 10,
    "новембар": 11,  "новембра": 11,
    "децембар": 12,  "децембра": 12,
}

_DOW = (
    r"(?:ponedeljak|utorak|sreda|četvrtak|petak|subota|nedelja|"
    r"понедељак|уторак|среда|четвртак|петак|субота|недеља)"
)

_REMOVE_TAGS = {"script", "style", "nav", "aside", "iframe", "noscript"}

# Schema.org types that are never useful as article metadata
_SCHEMA_SKIP = frozenset({
    "BreadcrumbList", "WebSite", "WebPage", "Organization",
    "SearchAction", "SiteNavigationElement", "ItemList",
})
_SCHEMA_ARTICLE = frozenset({
    "Article", "NewsArticle", "BlogPosting", "ReportageNewsArticle",
    "AnalysisNewsArticle", "OpinionNewsArticle",
})


def cyrillic_to_latin(text: str) -> str:
    return "".join(_CYR.get(ch, ch) for ch in text)


def parse_sr_date(text: str, default_year: Optional[int] = None) -> Optional[datetime]:
    """Parse Serbian date strings into datetime.

    Handles:
    - ISO 8601: "2026-06-17T16:00:00+02:00"
    - DD.MM.YYYY: "17.06.2026"
    - "18. jun 2026. u 14:32"
    - "среда, 17. јун 2026, 20:07"
    - "17. jun. 2026. 16:03"
    - Partial "17. juni" (needs default_year)
    """
    if not text:
        return None
    text = text.strip()

    # ISO 8601 with optional timezone
    iso = re.match(r"(\d{4}-\d{2}-\d{2})[T ](\d{2}:\d{2}(?::\d{2})?)", text)
    if iso:
        dt_str = f"{iso.group(1)} {iso.group(2)}"
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
            try:
                return datetime.strptime(dt_str, fmt)
            except ValueError:
                continue

    # Pure YYYY-MM-DD
    if re.match(r"^\d{4}-\d{2}-\d{2}$", text):
        try:
            return datetime.strptime(text, "%Y-%m-%d")
        except ValueError:
            pass

    # DD.MM.YYYY. HH:MMh — e.g. "18.06.2026. 10:09h" (Mondo format)
    dmy_time = re.search(r"(\d{1,2})\.\s*(\d{1,2})\.\s*(\d{4})\.?\s+(\d{1,2}):(\d{2})h?", text)
    if dmy_time:
        try:
            return datetime(
                int(dmy_time.group(3)), int(dmy_time.group(2)), int(dmy_time.group(1)),
                int(dmy_time.group(4)), int(dmy_time.group(5)),
            )
        except ValueError:
            pass

    # DD.MM.YYYY or DD. MM. YYYY (with optional spaces)
    dmy = re.search(r"(\d{1,2})\.\s*(\d{1,2})\.\s*(\d{4})", text)
    if dmy:
        try:
            return datetime(int(dmy.group(3)), int(dmy.group(2)), int(dmy.group(1)))
        except ValueError:
            pass

    # Normalize: strip day-of-week prefix, lowercase
    cleaned = re.sub(rf"^{_DOW},?\s*", "", text, flags=re.IGNORECASE).strip().lower()

    # "18. jun 2026. u 14:32" / "17. jun. 2026. 16:03"
    with_time = re.search(
        r"(\d{1,2})\.\s*([\w.]+?)\s*(\d{4})\.?\s*(?:u\s*)?(\d{1,2}):(\d{2})",
        cleaned,
    )
    if with_time:
        month = _MONTHS.get(with_time.group(2).rstrip("."))
        if month:
            try:
                return datetime(
                    int(with_time.group(3)), month, int(with_time.group(1)),
                    int(with_time.group(4)), int(with_time.group(5)),
                )
            except ValueError:
                pass

    # "18. jun 2026"
    without_time = re.search(r"(\d{1,2})\.\s*([\w.]+?)\s*(\d{4})", cleaned)
    if without_time:
        month = _MONTHS.get(without_time.group(2).rstrip("."))
        if month:
            try:
                return datetime(int(without_time.group(3)), month, int(without_time.group(1)))
            except ValueError:
                pass

    # Partial: "17. juni" (no year) — use default_year if provided
    if default_year:
        partial = re.search(r"(\d{1,2})\.\s*([\w]+)", cleaned)
        if partial:
            month = _MONTHS.get(partial.group(2).rstrip("."))
            if month:
                try:
                    return datetime(default_year, month, int(partial.group(1)))
                except ValueError:
                    pass

    return None


def clean_text(element: Tag) -> str:
    """Extract clean text from a BS4 element.

    Removes script/style/nav/aside/iframe/noscript, collapses whitespace,
    and deduplicates consecutive identical lines.
    """
    if element is None:
        return ""
    # Re-parse to avoid mutating the original tree
    local = BeautifulSoup(str(element), "lxml")
    for tag in local.find_all(_REMOVE_TAGS):
        tag.decompose()
    raw = local.get_text(separator="\n")
    lines = [ln.strip() for ln in raw.splitlines() if ln.strip()]
    result: list[str] = []
    for ln in lines:
        if not result or ln != result[-1]:
            result.append(ln)
    return "\n".join(result)


def extract_schema_org(soup: BeautifulSoup) -> Optional[dict]:
    """Return the first Article/NewsArticle JSON-LD block.

    Never returns BreadcrumbList, WebSite, WebPage, Organization, etc.
    Falls back to the first non-skip-type block only if no Article is found.
    """
    all_items: list[dict] = []
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            raw = (script.string or "").strip()
            if not raw:
                continue
            data = json.loads(raw)
            candidates = data if isinstance(data, list) else [data]
            all_items.extend(c for c in candidates if isinstance(c, dict))
        except (json.JSONDecodeError, TypeError):
            continue

    def _types(item: dict) -> list[str]:
        t = item.get("@type", "")
        return t if isinstance(t, list) else [t]

    # First pass: Article/NewsArticle types
    for item in all_items:
        if any(any(at in ti for at in _SCHEMA_ARTICLE) for ti in _types(item)):
            return item

    # Second pass: any non-skip type
    for item in all_items:
        if not any(ti in _SCHEMA_SKIP for ti in _types(item)):
            return item

    return None


def unique_urls(urls: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for u in urls:
        if u not in seen:
            seen.add(u)
            result.append(u)
    return result
