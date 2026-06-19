"""MediaScope scraper scheduler.

Runs all scrapers on hourly cron with 3-minute staggered starts.
N1 at :00, Blic at :03, Telegraf at :06 ... Politika at :57.

Usage:
    python -m backend.scrapers.scheduler          # start scheduler (blocking)
    python -m backend.scrapers.scheduler --list   # show schedule
"""
from __future__ import annotations

import logging
import os
import sys
from datetime import datetime
from typing import Optional

# Allow importing db.py from backend/ regardless of how scheduler is invoked
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import db  # noqa: E402 — must follow sys.path insertion

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

from .sources import SCRAPERS, STAGGERED_ORDER

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("mediascope.scheduler")


def _run_scraper(source_id: str) -> None:
    """Run a single scraper and persist results to DB. Called by APScheduler."""
    scraper_cls = SCRAPERS.get(source_id)
    if not scraper_cls:
        logger.error("Unknown source_id: %s", source_id)
        return

    scraper = scraper_cls()
    start = datetime.utcnow()
    logger.info("[%s] Run started", source_id)

    try:
        urls = scraper.get_article_urls()
        logger.info("[%s] Found %d URLs", source_id, len(urls))

        new_count = 0
        updated = 0
        failed = 0
        for url in urls:
            try:
                article = scraper.parse_article(url)
                if article:
                    is_new = db.save_article(article)
                    if is_new:
                        new_count += 1
                    else:
                        updated += 1
                else:
                    failed += 1
            except Exception as exc:
                logger.error("[%s] Error parsing %s: %s", source_id, url, exc)
                failed += 1

        elapsed = (datetime.utcnow() - start).total_seconds()
        logger.info(
            "[%s] Run complete — new=%d updated=%d failed=%d elapsed=%.1fs",
            source_id, new_count, updated, failed, elapsed,
        )
    except Exception as exc:
        logger.exception("[%s] Unhandled exception during run: %s", source_id, exc)


def build_scheduler() -> BlockingScheduler:
    db.init_db()  # ensure tables exist before any job fires
    scheduler = BlockingScheduler(timezone="Europe/Belgrade")

    for idx, source_id in enumerate(STAGGERED_ORDER):
        minute_offset = idx * 3  # 3-minute gaps; 20 sources × 3 = 60 min (fits in 1h)
        trigger = CronTrigger(minute=str(minute_offset))
        scheduler.add_job(
            func=_run_scraper,
            trigger=trigger,
            args=[source_id],
            id=f"scrape_{source_id}",
            name=f"Scrape {source_id}",
            misfire_grace_time=120,  # allow 2-minute late start
            coalesce=True,
        )
        logger.info(
            "Scheduled [%s] at :%02d every hour",
            source_id, minute_offset,
        )

    return scheduler


def print_schedule() -> None:
    print(f"\n{'Source':<12} {'Minute':>8}  {'Cron'}")
    print("-" * 32)
    for idx, source_id in enumerate(STAGGERED_ORDER):
        minute = idx * 3
        print(f"{source_id:<12} :{minute:02d}       0 {minute} * * *")
    print()


if __name__ == "__main__":
    if "--list" in sys.argv:
        print_schedule()
        sys.exit(0)

    logger.info("Starting MediaScope scheduler — %d sources configured", len(STAGGERED_ORDER))
    scheduler = build_scheduler()
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Scheduler stopped")
