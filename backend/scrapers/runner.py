"""MediaScope scraper runner — CLI tool for running scrapers manually.

Usage:
    python runner.py --all                  Run all scrapers (save to DB)
    python runner.py --source telegraf      Run one scraper (save to DB)
    python runner.py --test telegraf        Test one scraper (print results, NO DB save)
    python runner.py --test-all             Test all scrapers (print results, NO DB save)
    python runner.py --list                 List all available scrapers
"""
from __future__ import annotations

import argparse
import dataclasses
import json
import logging
import sys
import time
from datetime import datetime
from typing import Optional

# Allow running as `python runner.py` from the backend/scrapers/ directory
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scrapers.sources import SCRAPERS, STAGGERED_ORDER
from scrapers.base import ArticleData, ScraperError
import db

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("mediascope.runner")


# ── helpers ──────────────────────────────────────────────────────────────────

def _article_to_dict(a: ArticleData) -> dict:
    d = dataclasses.asdict(a)
    # Convert datetime fields to ISO strings for JSON serialization
    for key in ("published_at", "updated_at", "scraped_at"):
        if d[key] is not None:
            d[key] = d[key].isoformat()
    return d


def _print_article(article: ArticleData) -> None:
    d = _article_to_dict(article)
    # Truncate long text fields for readability
    for field in ("text", "text_raw"):
        if d[field] and len(d[field]) > 500:
            d[field] = d[field][:500] + f"… [{len(d[field])} chars total]"
    print(json.dumps(d, ensure_ascii=False, indent=2))


def _print_separator(source_id: str) -> None:
    print(f"\n{'=' * 60}")
    print(f"  SOURCE: {source_id}")
    print(f"{'=' * 60}\n")


# ── test mode ─────────────────────────────────────────────────────────────────

def run_test(source_id: str) -> bool:
    """Test-mode: print results, no DB save. Returns True if at least one article parsed."""
    scraper_cls = SCRAPERS.get(source_id)
    if not scraper_cls:
        print(f"ERROR: unknown source '{source_id}'. Use --list to see available sources.")
        return False

    _print_separator(source_id)
    scraper = scraper_cls()
    errors: list[str] = []

    # Step 1: Get URLs
    print(f"[1/3] Fetching article URLs from {source_id}...")
    start = time.monotonic()
    try:
        urls = scraper.get_article_urls()
    except Exception as exc:
        errors.append(f"get_article_urls failed: {exc}")
        urls = []
    elapsed = time.monotonic() - start
    print(f"      → {len(urls)} URL(s) found in {elapsed:.1f}s")

    if urls:
        print(f"      First 5 URLs:")
        for u in urls[:5]:
            print(f"        {u}")
        if len(urls) > 5:
            print(f"        … and {len(urls) - 5} more")

    # Step 2: Parse first article
    article: Optional[ArticleData] = None
    if urls:
        print(f"\n[2/3] Parsing first article: {urls[0]}")
        start = time.monotonic()
        try:
            article = scraper.parse_article(urls[0])
        except Exception as exc:
            errors.append(f"parse_article failed: {exc}")
        elapsed = time.monotonic() - start
        if article:
            print(f"      → Parsed in {elapsed:.1f}s")
            print(f"\n[3/3] ArticleData:\n")
            _print_article(article)
        else:
            print(f"      → parse_article returned None ({elapsed:.1f}s)")
            errors.append("parse_article returned None for first URL")
    else:
        print(f"\n[2/3] Skipped — no URLs found")
        print(f"[3/3] Skipped — no article to parse")

    # Step 3: Errors summary
    if errors:
        print(f"\nERRORS ({len(errors)}):")
        for e in errors:
            print(f"  ✗ {e}")
    else:
        print(f"\nNo errors.")

    return article is not None


def run_test_all() -> None:
    """Test all scrapers sequentially."""
    results: dict[str, bool] = {}
    for source_id in STAGGERED_ORDER:
        success = run_test(source_id)
        results[source_id] = success
        time.sleep(1)  # brief pause between scrapers

    print(f"\n{'=' * 60}")
    print(f"  TEST SUMMARY — {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC")
    print(f"{'=' * 60}")
    ok = [s for s, v in results.items() if v]
    fail = [s for s, v in results.items() if not v]
    print(f"  OK    ({len(ok)}): {', '.join(ok) if ok else '—'}")
    print(f"  FAIL  ({len(fail)}): {', '.join(fail) if fail else '—'}")
    print()


# ── production mode ───────────────────────────────────────────────────────────

def run_source(source_id: str) -> None:
    """Production run — save articles to DB (DB integration TODO)."""
    scraper_cls = SCRAPERS.get(source_id)
    if not scraper_cls:
        logger.error("Unknown source: %s", source_id)
        return

    db.init_db()
    scraper = scraper_cls()
    logger.info("[%s] Starting run", source_id)
    start = time.monotonic()

    try:
        urls = scraper.get_article_urls()
    except Exception as exc:
        logger.error("[%s] get_article_urls failed: %s", source_id, exc)
        return

    logger.info("[%s] %d URLs found", source_id, len(urls))

    saved = updated = failed = 0
    for url in urls:
        try:
            article = scraper.parse_article(url)
            if article:
                is_new = db.save_article(article)
                if is_new:
                    saved += 1
                else:
                    updated += 1
                logger.debug("[%s] %s: %s", source_id, "saved" if is_new else "updated", url)
            else:
                failed += 1
                logger.warning("[%s] parse_article returned None: %s", source_id, url)
        except ScraperError as exc:
            failed += 1
            logger.error("[%s] ScraperError [%s] for %s: %s", source_id, exc.error_type.value, url, exc)
        except Exception as exc:
            failed += 1
            logger.exception("[%s] Unexpected error for %s: %s", source_id, url, exc)

    elapsed = time.monotonic() - start
    logger.info(
        "[%s] Done — new=%d updated=%d failed=%d elapsed=%.1fs",
        source_id, saved, updated, failed, elapsed,
    )


def run_all() -> None:
    db.init_db()
    logger.info("Running all %d scrapers", len(STAGGERED_ORDER))
    for source_id in STAGGERED_ORDER:
        run_source(source_id)
    print_stats()


def print_stats(hours: int = 24) -> None:
    stats = db.get_stats(hours=hours)
    total = db.get_total()
    print(f"\n{'=' * 60}")
    print(f"  STATS — last {hours}h  (total in DB: {total})")
    print(f"{'=' * 60}")
    if stats:
        for row in stats:
            print(f"  {row['source_id']:<14} {row['count']:>4} articles")
    else:
        print("  (no articles yet)")
    print()


# ── CLI ───────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="MediaScope scraper runner",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--all", action="store_true", help="Run all scrapers (save to DB)")
    group.add_argument("--source", metavar="SOURCE_ID", help="Run one scraper (save to DB)")
    group.add_argument("--test", metavar="SOURCE_ID", help="Test one scraper (print, no DB)")
    group.add_argument("--test-all", action="store_true", help="Test all scrapers (print, no DB)")
    group.add_argument("--list", action="store_true", help="List available scrapers")
    group.add_argument("--stats", action="store_true", help="Show DB stats (last 24h)")

    args = parser.parse_args()

    if args.stats:
        db.init_db()
        print_stats()

    elif args.list:
        print("\nAvailable scrapers:")
        for idx, source_id in enumerate(STAGGERED_ORDER):
            cls = SCRAPERS[source_id]
            supported = not hasattr(cls, "_reason")
            status = "✓ supported" if supported else "⚠ stub (see source)"
            print(f"  {idx+1:2}. {source_id:<12} {status}")
        print()

    elif args.all:
        run_all()

    elif args.source:
        run_source(args.source)

    elif args.test:
        success = run_test(args.test)
        sys.exit(0 if success else 1)

    elif args.test_all:
        run_test_all()


if __name__ == "__main__":
    main()
