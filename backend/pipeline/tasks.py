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
REDIS_KEY_PAUSED = "mediascope:pipeline:paused"
BATCH_SIZE = 3000  # max clanaka po batch-u — pokriva jedan ceo dan (Anthropic limit je 10k)


def _redis() -> redis_lib.Redis:
    return redis_lib.from_url(settings.REDIS_URL, decode_responses=True)


def _run_async(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


async def _load_catalogs() -> tuple:
    """Ucitava framing + narrative kataloge iz baze. Vraca (framing_text, narrative_text)."""
    from pipeline.prompts import build_framing_catalog_text, build_narrative_catalog_text

    pg = await asyncpg.connect(PG_DSN)
    try:
        framing_rows = await pg.fetch(
            """
            SELECT ft.name, ft.description, t.key AS topic_key
            FROM framing_types ft
            LEFT JOIN topics t ON t.id = ft.topic_id
            WHERE ft.is_validated = TRUE
            ORDER BY t.key NULLS FIRST, ft.name
            """
        )
        narrative_rows = await pg.fetch(
            """
            SELECT id, name, narrative_type, description
            FROM narratives
            WHERE is_active = TRUE AND is_validated = TRUE
            ORDER BY id
            LIMIT $1
            """,
            settings.NARRATIVE_CATALOG_MAX,
        )
        framing_text = build_framing_catalog_text([dict(r) for r in framing_rows]) if framing_rows else ""
        narrative_text = build_narrative_catalog_text([dict(r) for r in narrative_rows]) if narrative_rows else ""
        return framing_text, narrative_text
    finally:
        await pg.close()


def _build_analysis_system():
    """Sklapa `system` (framing + narrative katalog + cache_control) za analizni poziv."""
    from pipeline.prompts import build_system

    framing_text, narrative_text = _run_async(_load_catalogs())
    return build_system(
        framing_text or None, narrative_text or None,
        enable_caching=settings.ENABLE_PROMPT_CACHING,
    )


async def _batch_log_submit(batch_id: str, batch_type: str, batch_date: str, article_count: int):
    pg = await asyncpg.connect(PG_DSN)
    try:
        await pg.execute(
            """
            INSERT INTO pipeline_batches (batch_id, batch_type, batch_date, status, article_count, submitted_at)
            VALUES ($1, $2, $3, 'submitted', $4, NOW())
            ON CONFLICT (batch_id) DO NOTHING
            """,
            batch_id, batch_type, batch_date, article_count,
        )
    finally:
        await pg.close()


async def _batch_log_finish(batch_id: str, status: str, articles_saved: int, articles_failed: int, error_message: str = None):
    pg = await asyncpg.connect(PG_DSN)
    try:
        await pg.execute(
            """
            UPDATE pipeline_batches
            SET status=$2, articles_saved=$3, articles_failed=$4, finished_at=NOW(), error_message=$5
            WHERE batch_id=$1
            """,
            batch_id, status, articles_saved, articles_failed, error_message,
        )
    finally:
        await pg.close()


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

    r = _redis()
    if r.get(REDIS_KEY_PAUSED):
        logger.info("Pipeline je pauziran — preskacemo nightly batch")
        return {"status": "skipped", "reason": "pipeline_paused"}

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
        batch_id = submit_analysis_batch(articles, system=_build_analysis_system())
    except Exception as exc:
        logger.exception("Greska pri submitu batch-a: %s", exc)
        raise self.retry(exc=exc, countdown=300)

    r.set(REDIS_KEY_BATCH_ID, batch_id, ex=86400)
    r.set(REDIS_KEY_BATCH_DATE, target.isoformat(), ex=86400)
    _run_async(_batch_log_submit(batch_id, "nightly", target.isoformat(), len(articles)))

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

    if _redis().get(REDIS_KEY_PAUSED):
        logger.info("Pipeline je pauziran — preskacemo catch-up batch")
        return {"status": "skipped", "reason": "pipeline_paused"}

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
        batch_id = submit_analysis_batch(articles, system=_build_analysis_system())
    except Exception as exc:
        logger.exception("Greska pri catch-up batch-u: %s", exc)
        raise self.retry(exc=exc, countdown=300)

    r.set(REDIS_KEY_BATCH_ID, batch_id, ex=86400)
    r.set(REDIS_KEY_BATCH_DATE, "catchup", ex=86400)
    _run_async(_batch_log_submit(batch_id, "catchup", "catchup", len(articles)))

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

    try:
        metrics = _run_async(process_batch_results(results))
        batch_status = "completed"
        batch_error = None
    except Exception as exc:
        logger.exception("Greska pri procesiranju batch-a %s: %s", batch_id, exc)
        metrics = {"saved": 0, "errors": len(results)}
        batch_status = "failed"
        batch_error = str(exc)[:500]

    _run_async(_batch_log_finish(batch_id, batch_status, metrics.get("saved", 0), metrics.get("errors", 0), batch_error))

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

    from pipeline.prompts import build_mvp_prompt

    if not settings.ANTHROPIC_API_KEY:
        return {"status": "error", "reason": "no_api_key"}

    system_val = _build_analysis_system()

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
                max_tokens=2500,
                system=system_val,
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


@celery.task(name="pipeline.tasks.detect_alerts")
def detect_alerts():
    """
    Detektuje koordinaciju, topic spikove i probleme sa scraperima.
    Kreira Alert zapise za nove nalaze. Pokrece se dnevno u 08:00.
    """
    logger.info("detect_alerts: pocinje")

    async def _run():
        from datetime import date, timedelta
        pg = await asyncpg.connect(PG_DSN)
        try:
            today = date.today().isoformat()
            yesterday = (date.today() - timedelta(days=1)).isoformat()
            alerts_created = 0

            async def _alert_exists(alert_type: str, alert_date: str) -> bool:
                return bool(await pg.fetchval(
                    "SELECT id FROM alerts WHERE alert_type=$1 AND date=$2 LIMIT 1",
                    alert_type, alert_date,
                ))

            async def _create_alert(alert_type, severity, title, description, score=None, source_ids=None, date_val=None):
                nonlocal alerts_created
                d = date_val or today
                if await _alert_exists(alert_type, d):
                    return
                await pg.execute(
                    """
                    INSERT INTO alerts (alert_type, severity, title, description, score, source_ids, date)
                    VALUES ($1, $2, $3, $4, $5, $6, $7)
                    """,
                    alert_type, severity, title, description,
                    float(score) if score is not None else None,
                    source_ids or [], d,
                )
                alerts_created += 1

            # 1. Koordinacioni alert — kopirani clanci (similarity >= 0.85, 4+ izvora)
            # NAPOMENA (Faza 0): tabela copy_similarity ne postoji u shemi — ova detekcija
            # je privremeno zasticena try/except-om i bice preusmerena na coordination_copypaste
            # u Fazi 3 (pravi embedding-based copy-paste). Do tada ne sme da obori ceo task.
            try:
                copy_groups = await pg.fetch(
                    """
                    SELECT
                        similarity_group,
                        COUNT(DISTINCT a.source_id) AS source_count,
                        MAX(cs.similarity_score) AS max_score,
                        ARRAY_AGG(DISTINCT a.source_id) AS sources,
                        MAX(a.title) AS sample_title
                    FROM copy_similarity cs
                    JOIN articles a ON a.id = cs.article_id
                    WHERE cs.similarity_score >= 0.85
                      AND a.published_at >= NOW() - INTERVAL '24 hours'
                    GROUP BY similarity_group
                    HAVING COUNT(DISTINCT a.source_id) >= 4
                    ORDER BY source_count DESC
                    LIMIT 5
                    """,
                )
                for g in copy_groups:
                    await _create_alert(
                        "coordination_copy",
                        "high" if g["source_count"] >= 6 else "medium",
                        f"Koordinisano kopiranje: {g['source_count']} portala",
                        f"Identičan ili gotovo identičan tekst detektovan na {g['source_count']} portala. "
                        f"Primer naslova: {g['sample_title'][:200]}",
                        score=g["max_score"],
                        source_ids=list(g["sources"]),
                    )
            except Exception as exc:
                logger.warning("coordination_copy detekcija preskocena (copy_similarity nedostupna): %s", exc)

            # 2. Topic spike — tema ima >200% vise clanaka nego 7-dnevni prosjek
            topic_spikes = await pg.fetch(
                """
                WITH daily AS (
                    SELECT
                        aa.primary_topic AS topic,
                        DATE(a.published_at) AS day,
                        COUNT(*) AS cnt
                    FROM article_analysis aa
                    JOIN articles a ON a.id = aa.article_id
                    WHERE a.published_at >= NOW() - INTERVAL '8 days'
                      AND aa.primary_topic IS NOT NULL
                    GROUP BY aa.primary_topic, DATE(a.published_at)
                ),
                baseline AS (
                    SELECT topic, AVG(cnt) AS avg_cnt
                    FROM daily WHERE day < CURRENT_DATE
                    GROUP BY topic
                ),
                today AS (
                    SELECT topic, cnt AS today_cnt
                    FROM daily WHERE day = CURRENT_DATE
                )
                SELECT t.topic, t.today_cnt, b.avg_cnt,
                       (t.today_cnt / NULLIF(b.avg_cnt, 0)) AS ratio
                FROM today t
                JOIN baseline b ON b.topic = t.topic
                WHERE t.today_cnt / NULLIF(b.avg_cnt, 0) >= 2.5
                  AND b.avg_cnt >= 3
                ORDER BY ratio DESC
                LIMIT 5
                """,
            )
            for spike in topic_spikes:
                ratio_pct = int((spike["ratio"] - 1) * 100)
                await _create_alert(
                    "topic_spike",
                    "medium",
                    f"Topic spike: {spike['topic']} (+{ratio_pct}%)",
                    f"Tema {spike['topic']} ima {spike['today_cnt']} clanaka danas vs "
                    f"prosek od {spike['avg_cnt']:.1f} — povecanje od {ratio_pct}%.",
                    score=float(spike["ratio"]),
                )

            # 3. Scraper gap — portal bez clanaka 48h
            silent_sources = await pg.fetch(
                """
                SELECT s.source_id, s.name,
                       MAX(a.scraped_at) AS last_scraped
                FROM sources s
                LEFT JOIN articles a ON a.source_id = s.source_id
                  AND a.scraped_at >= NOW() - INTERVAL '7 days'
                WHERE s.is_active = TRUE
                GROUP BY s.source_id, s.name
                HAVING MAX(a.scraped_at) < NOW() - INTERVAL '48 hours'
                   OR MAX(a.scraped_at) IS NULL
                """,
            )
            for src in silent_sources:
                await _create_alert(
                    f"scraper_gap_{src['source_id']}",
                    "low",
                    f"Scraper gap: {src['name']}",
                    f"Portal {src['name']} ({src['source_id']}) nema novih clanaka >48h.",
                    source_ids=[src["source_id"]],
                    date_val=today,
                )

            return {"alerts_created": alerts_created}
        finally:
            await pg.close()

    result = _run_async(_run())
    logger.info("detect_alerts zavrsen: %s", result)
    return result


@celery.task(name="pipeline.tasks.compute_narrative_matching")
def compute_narrative_matching():
    """
    Agregira narrative_daily_intensity iz article_narratives (koje popunjava AI mapiranje
    u processor-u). Cista SQL agregacija — bez ILIKE, bez AI. Pokrece se dnevno (06:00).

    NAPOMENA: mapiranje clanaka na narative se sada radi AI-jem tokom analize (Faza 2),
    ne keyword pretragom. Ovaj task samo preracunava dnevni intenzitet.
    """
    logger.info("compute_narrative_matching (agregacija): pocinje")

    async def _run():
        pg = await asyncpg.connect(PG_DSN)
        try:
            # Preracunaj intenzitet za poslednjih 90 dana iz postojecih article_narratives veza.
            await pg.execute(
                """
                INSERT INTO narrative_daily_intensity
                    (narrative_id, source_id, date, article_count, avg_confidence, intensity_score)
                SELECT
                    an.narrative_id,
                    a.source_id,
                    DATE(a.published_at) AS date,
                    COUNT(*) AS article_count,
                    AVG(an.confidence) AS avg_confidence,
                    COUNT(*)::float * COALESCE(AVG(an.confidence), 0) AS intensity_score
                FROM article_narratives an
                JOIN articles a ON a.id = an.article_id
                JOIN narratives n ON n.id = an.narrative_id AND n.is_active = TRUE
                WHERE a.published_at >= NOW() - INTERVAL '90 days'
                GROUP BY an.narrative_id, a.source_id, DATE(a.published_at)
                ON CONFLICT (narrative_id, source_id, date) DO UPDATE SET
                    article_count = EXCLUDED.article_count,
                    avg_confidence = EXCLUDED.avg_confidence,
                    intensity_score = EXCLUDED.intensity_score
                """
            )
            rows = await pg.fetchval("SELECT COUNT(*) FROM narrative_daily_intensity")
            return {"intensity_rows": rows}
        finally:
            await pg.close()

    result = _run_async(_run())
    logger.info("compute_narrative_matching zavrsen: %s", result)
    return result


@celery.task(name="pipeline.tasks.apply_calibration_feedback")
def apply_calibration_feedback():
    """
    Agregira neaplicirani feedback analitičara i dodaje korekcije u SYSTEM_PROMPT varijablu (in-memory).
    Oznaci feedback kao applied_to_pipeline = True.
    Pokrece se nedeljno.
    """
    logger.info("apply_calibration_feedback: pocinje")

    async def _run():
        pg = await asyncpg.connect(PG_DSN)
        try:
            rows = await pg.fetch(
                """
                SELECT analysis_type, is_correct, original_value, corrected_value, comment
                FROM calibration_feedback
                WHERE applied_to_pipeline = FALSE
                ORDER BY created_at DESC
                LIMIT 500
                """,
            )
            if not rows:
                logger.info("Nema novih feedbackova za procesiranje")
                return {"processed": 0}

            # Grupiraj po analysis_type
            from collections import defaultdict
            groups = defaultdict(list)
            for r in rows:
                groups[r["analysis_type"]].append(dict(r))

            # Generiši summary korekcija
            corrections = []
            for atype, items in groups.items():
                wrong = [i for i in items if not i["is_correct"]]
                if not wrong:
                    continue
                examples = wrong[:5]
                ex_str = ", ".join(
                    f"'{e['original_value']}' -> '{e['corrected_value']}'" if e.get("corrected_value") else f"'{e['original_value']}' (netacno)"
                    for e in examples if e.get("original_value")
                )
                if ex_str:
                    corrections.append(f"{atype}: {len(wrong)} korekcija (primeri: {ex_str})")

            if corrections:
                correction_note = "\n\nKorekcije analitičara (primeni pri sledecoj analizi):\n" + "\n".join(f"- {c}" for c in corrections)
                import pipeline.prompts as prompts_module
                if not hasattr(prompts_module, '_calibration_note'):
                    prompts_module._calibration_note = ""
                prompts_module._calibration_note = correction_note
                original_system = prompts_module.SYSTEM_PROMPT
                if "\n\nKorekcije analitičara" in original_system:
                    prompts_module.SYSTEM_PROMPT = original_system.split("\n\nKorekcije analitičara")[0] + correction_note
                else:
                    prompts_module.SYSTEM_PROMPT = original_system + correction_note
                logger.info("Dodate korekcije u SYSTEM_PROMPT: %d tipova", len(corrections))

            # Označi sve kao aplicirane
            status = await pg.execute(
                "UPDATE calibration_feedback SET applied_to_pipeline=TRUE WHERE applied_to_pipeline=FALSE"
            )
            count = len(rows)

            logger.info("Aplicirano %d feedbackova", count)
            return {"processed": len(rows), "corrections": len(corrections)}
        finally:
            await pg.close()

    result = _run_async(_run())
    logger.info("apply_calibration_feedback zavrsen: %s", result)
    return result


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
