"""
Celery taskovi za AI pipeline.

Nocni tok:
  22:30  submit_nightly_batch()  -> submituje batch Anthropic API-ju, cuva batch_id u Redis
  */15   check_and_process_batch() -> proverava status, ako je done -> process_batch_results()

Rucno pokretanje (dev/test):
  from pipeline.tasks import run_batch_for_articles
  run_batch_for_articles.delay([123, 456, 789])
"""

import asyncio
import json
import logging
from datetime import date, datetime, timezone

import asyncpg
import redis as redis_lib

from celery_app import celery
from config import settings
from pipeline.batch_api import submit_analysis_batch, get_batch_status, iter_batch_results
from pipeline.prepare import prepare_article
from pipeline.processor import process_batch_results
from pipeline.summary import _fetch_daily_stats, generate_summary, REDIS_KEY, REDIS_TTL

logger = logging.getLogger(__name__)

PG_DSN = settings.DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")
REDIS_KEY_BATCH_ID = "mediascope:pipeline:current_batch_id"
REDIS_KEY_BATCH_DATE = "mediascope:pipeline:current_batch_date"
BATCH_SIZE = 3000  # max clanaka po batch-u — pokriva jedan ceo dan (Anthropic limit je 10k)


def _redis() -> redis_lib.Redis:
    return redis_lib.from_url(settings.REDIS_URL, decode_responses=True)


def _run_async(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


async def _fetch_unanalyzed_articles(limit: int = BATCH_SIZE, target_date: date = None) -> list[dict]:
    """Dohvata clanke koji jos nisu analizirani.

    Ako je target_date zadat, uzima samo clanke za taj dan (nightly mod).
    Inace uzima sve neobradjene, od najnovijeg (catch-up mod).
    """
    pg = await asyncpg.connect(PG_DSN)
    try:
        if target_date is not None:
            from datetime import timedelta
            next_date = target_date + timedelta(days=1)
            rows = await pg.fetch(
                """
                SELECT a.id, a.source_id, a.title, a.subtitle, a.text_content,
                       a.category, a.published_at
                FROM articles a
                LEFT JOIN article_analysis aa ON a.id = aa.article_id
                WHERE aa.id IS NULL
                  AND a.text_content IS NOT NULL
                  AND length(a.text_content) > 100
                  AND a.published_at >= $2
                  AND a.published_at < $3
                ORDER BY a.published_at DESC
                LIMIT $1
                """,
                limit, target_date, next_date,
            )
        else:
            rows = await pg.fetch(
                """
                SELECT a.id, a.source_id, a.title, a.subtitle, a.text_content,
                       a.category, a.published_at
                FROM articles a
                LEFT JOIN article_analysis aa ON a.id = aa.article_id
                WHERE aa.id IS NULL
                  AND a.text_content IS NOT NULL
                  AND length(a.text_content) > 100
                ORDER BY a.scraped_at DESC
                LIMIT $1
                """,
                limit,
            )
        return [dict(r) for r in rows]
    finally:
        await pg.close()


@celery.task(name="pipeline.tasks.submit_nightly_batch", bind=True, max_retries=3)
def submit_nightly_batch(self, target_date_str: str = None):
    """
    Nocni task. Submituje sve neprocesirane clanke prethodnog dana Anthropic Batch API-ju.
    Ako je aktivan batch, preskace (check_and_process_batch ce ga pokupiti).
    """
    logger.info("submit_nightly_batch: pocinje")

    if not settings.ANTHROPIC_API_KEY:
        logger.error("ANTHROPIC_API_KEY nije konfigurisan — preskacemo batch")
        return {"status": "skipped", "reason": "no_api_key"}

    # Proveravamo da li vec postoji aktivan batch koji se obradjuje
    r = _redis()
    existing_batch = r.get(REDIS_KEY_BATCH_ID)
    if existing_batch:
        logger.info("Vec postoji aktivan batch %s — preskacemo submit", existing_batch)
        return {"status": "skipped", "reason": "batch_in_progress", "batch_id": existing_batch}

    # Targetujemo prethodni dan (ili zadati datum)
    from datetime import timedelta
    if target_date_str:
        target = date.fromisoformat(target_date_str)
    else:
        target = date.today() - timedelta(days=1)

    articles_raw = _run_async(_fetch_unanalyzed_articles(BATCH_SIZE, target_date=target))
    if not articles_raw:
        logger.info("Nema novih clanaka za %s", target)
        return {"status": "skipped", "reason": "no_articles", "date": target.isoformat()}

    articles = [prepare_article(a) for a in articles_raw]
    logger.info("Submitujemo %d clanaka za %s Anthropic Batch API-ju", len(articles), target)

    try:
        batch_id = submit_analysis_batch(articles)
    except Exception as exc:
        logger.exception("Greska pri submitu batch-a: %s", exc)
        raise self.retry(exc=exc, countdown=300)

    r.set(REDIS_KEY_BATCH_ID, batch_id, ex=86400)
    r.set(REDIS_KEY_BATCH_DATE, target.isoformat(), ex=86400)

    logger.info("Batch submitovan: %s (%d clanaka za %s)", batch_id, len(articles), target)
    return {"status": "submitted", "batch_id": batch_id, "article_count": len(articles), "date": target.isoformat()}


@celery.task(name="pipeline.tasks.submit_catchup_batches", bind=True, max_retries=3)
def submit_catchup_batches(self):
    """
    Catch-up task za istorijski backlog — submituje batch od BATCH_SIZE neobradjenih clanaka.
    Pokreci rucno dok god ima backlog-a. Svaki poziv submituje jedan batch.
    Posle svakog batch-a, check_and_process_batch ce preuzeti rezultate.
    """
    logger.info("submit_catchup_batches: pocinje")

    if not settings.ANTHROPIC_API_KEY:
        return {"status": "skipped", "reason": "no_api_key"}

    r = _redis()
    existing_batch = r.get(REDIS_KEY_BATCH_ID)
    if existing_batch:
        logger.info("Vec postoji aktivan batch %s — sacekaj da se zavrsi", existing_batch)
        return {"status": "skipped", "reason": "batch_in_progress", "batch_id": existing_batch}

    # Bez date filtera — uzima najnovije neobradjene (catch-up mod)
    articles_raw = _run_async(_fetch_unanalyzed_articles(BATCH_SIZE))
    if not articles_raw:
        logger.info("Catch-up zavrsen — nema vise neobradjenih clanaka")
        return {"status": "done", "reason": "no_more_articles"}

    articles = [prepare_article(a) for a in articles_raw]
    logger.info("Catch-up: submitujemo %d clanaka", len(articles))

    try:
        batch_id = submit_analysis_batch(articles)
    except Exception as exc:
        logger.exception("Greska pri catch-up batch-u: %s", exc)
        raise self.retry(exc=exc, countdown=300)

    r.set(REDIS_KEY_BATCH_ID, batch_id, ex=86400)
    r.set(REDIS_KEY_BATCH_DATE, "catchup", ex=86400)

    logger.info("Catch-up batch submitovan: %s (%d clanaka)", batch_id, len(articles))
    return {"status": "submitted", "batch_id": batch_id, "article_count": len(articles)}


@celery.task(name="pipeline.tasks.check_and_process_batch", bind=True)
def check_and_process_batch(self):
    """
    Proverava status tekuceg batch-a.
    Ako je zavrsen, preuzima i procesira rezultate.
    """
    r = _redis()
    batch_id = r.get(REDIS_KEY_BATCH_ID)

    if not batch_id:
        return {"status": "no_batch"}

    status_info = get_batch_status(batch_id)
    logger.info("Batch %s status: %s", batch_id, status_info["status"])

    if status_info["status"] != "ended":
        return {"status": "in_progress", "batch_id": batch_id, **status_info}

    # Batch je gotov — preuzmi i procesiraj
    logger.info("Batch zavrsen, preuzimamo rezultate...")
    results = list(iter_batch_results(batch_id))

    metrics = _run_async(process_batch_results(results))

    # Obrisi batch_id iz Redis-a (ne bi trebalo da ga processujemo dva puta)
    r.delete(REDIS_KEY_BATCH_ID)

    logger.info(
        "Batch %s procesiran: saved=%d, errors=%d",
        batch_id,
        metrics["saved"],
        metrics["errors"],
    )
    return {
        "status": "processed",
        "batch_id": batch_id,
        "metrics": metrics,
    }


@celery.task(name="pipeline.tasks.run_batch_for_articles")
def run_batch_for_articles(article_ids: list[int]):
    """
    Rucno pokretanje analize za specificne clanke (dev/test/re-analiza).
    Sinhrono — ceka na rezultate (ne koristi Batch API, direktno).
    """
    import anthropic
    import json

    from pipeline.prompts import SYSTEM_PROMPT, build_mvp_prompt

    if not settings.ANTHROPIC_API_KEY:
        return {"status": "error", "reason": "no_api_key"}

    async def fetch_articles(ids):
        pg = await asyncpg.connect(PG_DSN)
        try:
            rows = await pg.fetch(
                """
                SELECT id, source_id, title, subtitle, text_content, category, published_at
                FROM articles WHERE id = ANY($1::bigint[])
                """,
                ids,
            )
            return [dict(r) for r in rows]
        finally:
            await pg.close()

    articles_raw = _run_async(fetch_articles(article_ids))
    articles = [prepare_article(a) for a in articles_raw]

    client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
    batch_results = []

    for article in articles:
        try:
            msg = client.messages.create(
                model=settings.ANTHROPIC_MODEL,
                max_tokens=2000,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": build_mvp_prompt(article)}],
            )
            raw_text = msg.content[0].text
            try:
                cleaned = raw_text.strip()
                if cleaned.startswith("```"):
                    lines = cleaned.split("\n")
                    cleaned = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:]).strip()
                parsed = json.loads(cleaned)
                batch_results.append((article["article_id"], parsed, None))
            except json.JSONDecodeError as e:
                batch_results.append((article["article_id"], None, f"JSON error: {e}"))
        except Exception as e:
            batch_results.append((article["article_id"], None, str(e)))

    metrics = _run_async(process_batch_results(batch_results))
    return {"status": "done", "metrics": metrics, "article_ids": article_ids}


@celery.task(name="pipeline.tasks.generate_morning_summary", bind=True, max_retries=2)
def generate_morning_summary(self, target_date: str = None):
    """
    Generise AI dnevni pregled i cuva u Redis.
    Pokrece se svako jutro u 07:00.
    """
    import asyncio
    from datetime import date

    if not settings.ANTHROPIC_API_KEY:
        return {"status": "skipped", "reason": "no_api_key"}

    target = date.fromisoformat(target_date) if target_date else date.today()
    redis_key = REDIS_KEY.format(date=target.isoformat())

    r = _redis()
    if r.exists(redis_key):
        logger.info("Summary za %s vec postoji u Redis-u", target)
        return {"status": "cached", "date": target.isoformat()}

    try:
        stats = asyncio.get_event_loop().run_until_complete(_fetch_daily_stats(target))
        if stats["analyzed_articles"] < 5:
            return {"status": "skipped", "reason": "insufficient_data", "analyzed": stats["analyzed_articles"]}

        summary = generate_summary(stats)
        summary["generated_at"] = datetime.now(timezone.utc).isoformat()

        r.set(redis_key, json.dumps(summary, ensure_ascii=False), ex=REDIS_TTL)
        logger.info("Summary za %s generisan i sacuvan u Redis", target)
        return {"status": "done", "date": target.isoformat()}

    except Exception as exc:
        logger.exception("Greska pri generisanju summary-ja: %s", exc)
        raise self.retry(exc=exc, countdown=300)
