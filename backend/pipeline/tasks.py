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
        calib_rows = await pg.fetch(
            "SELECT prompt_text FROM calibration_prompts WHERE is_active = TRUE ORDER BY analysis_type, version"
        )
        framing_text = build_framing_catalog_text([dict(r) for r in framing_rows]) if framing_rows else ""
        narrative_text = build_narrative_catalog_text([dict(r) for r in narrative_rows]) if narrative_rows else ""
        calibration_text = "\n\n".join(r["prompt_text"] for r in calib_rows) if calib_rows else ""
        return framing_text, narrative_text, calibration_text
    finally:
        await pg.close()


def _build_analysis_system():
    """Sklapa `system` (kalibracija + framing + narrative katalog + cache_control)."""
    from pipeline.prompts import build_system

    framing_text, narrative_text, calibration_text = _run_async(_load_catalogs())
    return build_system(
        framing_text or None, narrative_text or None, calibration_text or None,
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


@celery.task(name="pipeline.tasks.generate_embeddings")
def generate_embeddings(limit: int = 500):
    """Generise lokalne embeddinge za analizirane clanke bez embedding-a.

    Pokrece se periodicno (i kao backfill). Tekst ne napusta infrastrukturu.
    """
    from pipeline.embeddings import embed_texts, build_embed_input

    async def _fetch(lim):
        pg = await asyncpg.connect(PG_DSN)
        try:
            rows = await pg.fetch(
                """
                SELECT a.id, a.title, a.text_content
                FROM articles a
                JOIN article_analysis aa ON aa.article_id = a.id
                LEFT JOIN article_embeddings e ON e.article_id = a.id
                WHERE e.id IS NULL AND a.text_content IS NOT NULL
                ORDER BY a.id DESC
                LIMIT $1
                """,
                lim,
            )
            return [dict(r) for r in rows]
        finally:
            await pg.close()

    async def _save(items, vectors):
        pg = await asyncpg.connect(PG_DSN)
        try:
            for it, vec in zip(items, vectors):
                await pg.execute(
                    """
                    INSERT INTO article_embeddings (article_id, embedding, model_used, created_at)
                    VALUES ($1, $2, $3, NOW())
                    ON CONFLICT (article_id) DO UPDATE SET
                        embedding = EXCLUDED.embedding, model_used = EXCLUDED.model_used
                    """,
                    it["id"], str(vec), settings.EMBEDDING_MODEL,
                )
        finally:
            await pg.close()

    async def _fetch_framing_proposals():
        pg = await asyncpg.connect(PG_DSN)
        try:
            return [dict(r) for r in await pg.fetch(
                """
                SELECT id, name, description FROM framing_type_proposals
                WHERE status = 'pending' AND embedding IS NULL
                ORDER BY id DESC LIMIT 100
                """
            )]
        finally:
            await pg.close()

    async def _save_framing_embeddings(fps, vectors):
        pg = await asyncpg.connect(PG_DSN)
        try:
            for fp, vec in zip(fps, vectors):
                await pg.execute(
                    "UPDATE framing_type_proposals SET embedding = $1::vector WHERE id = $2",
                    "[" + ",".join(f"{v:.6f}" for v in vec) + "]", fp["id"],
                )
        finally:
            await pg.close()

    items = _run_async(_fetch(limit))
    if not items:
        articles_embedded = 0
    else:
        texts = [build_embed_input(it["title"], it["text_content"]) for it in items]
        vectors = embed_texts(texts, is_query=False)
        _run_async(_save(items, vectors))
        articles_embedded = len(items)
        logger.info("generate_embeddings: %d clanaka embedovano", articles_embedded)

    # Backfill embeddinga za pending framing predloge bez embeddinga
    fp_items = _run_async(_fetch_framing_proposals())
    if fp_items:
        fp_texts = [f"{fp['name']}. {fp['description'] or ''}".strip() for fp in fp_items]
        fp_vectors = embed_texts(fp_texts, is_query=False)
        _run_async(_save_framing_embeddings(fp_items, fp_vectors))
        logger.info("generate_embeddings: %d framing predloga embedovano", len(fp_items))

    return {"status": "ok", "embedded": articles_embedded, "framing_proposals_embedded": len(fp_items)}


@celery.task(name="pipeline.tasks.consolidate_narrative_proposals")
def consolidate_narrative_proposals(cosine_threshold: float = 0.15, batch_size: int = 1000):
    """Klasteruje narativne predloge semantički koristeći pgvector cosine distance.

    Za svaki neklastriran predlog:
    1. Generiše embedding (name + description)
    2. Traži najbliži pending klaster (cosine_distance < cosine_threshold)
    3. Ako nađe: dodaje predlog u klaster, ažurira centroid (running average)
    4. Ako ne nađe: kreira novi klaster
    """
    from pipeline.embeddings import embed_texts
    import psycopg2

    conn = psycopg2.connect(PG_DSN)
    conn.autocommit = False
    cur = conn.cursor()

    try:
        # Fetch unassigned pending proposals in batches
        cur.execute("""
            SELECT id, name, narrative_type, description
            FROM narrative_proposals
            WHERE status = 'pending' AND cluster_id IS NULL
            ORDER BY id
            LIMIT %s
        """, (batch_size,))
        proposals = cur.fetchall()

        if not proposals:
            conn.close()
            return {"status": "ok", "clustered": 0}

        # Generate embeddings for all at once (batch)
        texts = [
            f"{row[1]}. {row[3] or ''}".strip()
            for row in proposals
        ]
        vectors = embed_texts(texts, is_query=False)

        clustered = 0
        new_clusters = 0

        for (prop_id, name, ntype, desc), vec in zip(proposals, vectors):
            vec_str = "[" + ",".join(f"{v:.6f}" for v in vec) + "]"

            # Find nearest pending cluster of the same narrative_type.
            # Centroid is kept FIXED (first-proposal anchor) to prevent drift.
            cur.execute("""
                SELECT id, proposal_count
                FROM narrative_clusters
                WHERE status = 'pending'
                  AND narrative_type = %s
                  AND centroid_embedding <=> %s::vector < %s
                ORDER BY centroid_embedding <=> %s::vector
                LIMIT 1
            """, (ntype or "thematic", vec_str, cosine_threshold, vec_str))
            row = cur.fetchone()

            if row:
                cluster_id, count = row
                # Centroid NOT updated — stays anchored to the first proposal
                cur.execute("""
                    UPDATE narrative_clusters
                    SET proposal_count = %s, last_seen = now()
                    WHERE id = %s
                """, (count + 1, cluster_id))
                cur.execute("UPDATE narrative_proposals SET cluster_id = %s, embedding = %s::vector WHERE id = %s",
                            (cluster_id, vec_str, prop_id))
                clustered += 1
                conn.commit()
                continue

            # No suitable cluster — create new one
            cur.execute("""
                INSERT INTO narrative_clusters (representative_name, narrative_type, centroid_embedding, proposal_count, status, first_seen, last_seen)
                VALUES (%s, %s, %s::vector, 1, 'pending', now(), now())
                RETURNING id
            """, (name, ntype or "thematic", vec_str))
            new_cluster_id = cur.fetchone()[0]
            cur.execute("UPDATE narrative_proposals SET cluster_id = %s, embedding = %s::vector WHERE id = %s",
                        (new_cluster_id, vec_str, prop_id))
            new_clusters += 1
            conn.commit()

        logger.info("consolidate_narrative_proposals: %d assigned, %d new clusters", clustered, new_clusters)
        return {"status": "ok", "clustered": clustered, "new_clusters": new_clusters}

    except Exception as e:
        conn.rollback()
        logger.error("consolidate_narrative_proposals failed: %s", e)
        raise
    finally:
        cur.close()
        conn.close()


@celery.task(name="pipeline.tasks.detect_copypaste")
def detect_copypaste():
    """Pravi copy-paste detekcija preko pgvector cosine slicnosti (lokalni embeddingi).

    Uporedjuje clanke u prozoru COPYPASTE_WINDOW_HOURS, razlicit izvor, cosine >= prag.
    Upisuje u coordination_copypaste; parovi >= alert prag -> alert.
    """
    thr = settings.COPYPASTE_THRESHOLD
    alert_thr = settings.COPYPASTE_ALERT_THRESHOLD
    window = settings.COPYPASTE_WINDOW_HOURS

    async def _run():
        pg = await asyncpg.connect(PG_DSN)
        try:
            # Recompute window: obrisi postojece parove za clanke u prozoru (idempotentno)
            await pg.execute(
                f"""
                DELETE FROM coordination_copypaste
                WHERE article_id_a IN (
                    SELECT a.id FROM articles a WHERE a.published_at >= NOW() - INTERVAL '{window} hours'
                ) OR article_id_b IN (
                    SELECT a.id FROM articles a WHERE a.published_at >= NOW() - INTERVAL '{window} hours'
                )
                """
            )
            pairs = await pg.fetch(
                f"""
                WITH recent AS (
                    SELECT e.article_id, e.embedding, a.source_id, a.title, s.owner_group
                    FROM article_embeddings e
                    JOIN articles a ON a.id = e.article_id
                    JOIN sources s ON s.source_id = a.source_id
                    WHERE a.published_at >= NOW() - INTERVAL '{window} hours'
                )
                SELECT r1.article_id AS a_id, r2.article_id AS b_id,
                       1 - (r1.embedding <=> r2.embedding) AS sim,
                       (r1.owner_group IS NOT DISTINCT FROM r2.owner_group) AS same_owner,
                       r1.source_id AS src_a, r2.source_id AS src_b,
                       r1.title AS title_a
                FROM recent r1
                JOIN recent r2
                  ON r1.article_id < r2.article_id
                 AND r1.source_id <> r2.source_id
                WHERE (r1.embedding <=> r2.embedding) <= {1 - thr}
                ORDER BY sim DESC
                LIMIT 2000
                """
            )

            inserted = 0
            for p in pairs:
                await pg.execute(
                    """
                    INSERT INTO coordination_copypaste
                        (article_id_a, article_id_b, similarity_score, same_owner_group, detected_at)
                    VALUES ($1, $2, $3, $4, NOW())
                    """,
                    p["a_id"], p["b_id"], float(p["sim"]), bool(p["same_owner"]),
                )
                inserted += 1

            # Alert za visoke slicnosti izmedju razlicitih vlasnickih grupa
            high = [p for p in pairs if p["sim"] >= alert_thr and not p["same_owner"]]
            alerts_created = 0
            if high:
                from datetime import date
                today = date.today()  # date objekat — asyncpg ga prima za DATE kolone; f-string daje YYYY-MM-DD
                # grupa: broj distinct izvora ukljucenih u visoke parove
                srcs = set()
                for p in high:
                    srcs.add(p["src_a"]); srcs.add(p["src_b"])
                exists = await pg.fetchval(
                    "SELECT id FROM alerts WHERE alert_type='coordination_copy' AND date=$1 LIMIT 1", today
                )
                if not exists and len(srcs) >= 3:
                    await pg.execute(
                        """
                        INSERT INTO alerts (alert_type, severity, title, description, score, source_ids, date)
                        VALUES ('coordination_copy', $1, $2, $3, $4, $5, $6)
                        """,
                        "high" if len(srcs) >= 5 else "medium",
                        f"Copy-paste koordinacija: {len(srcs)} portala",
                        f"Visoka tekstualna slicnost (>= {int(alert_thr*100)}%) izmedju {len(high)} parova "
                        f"clanaka na {len(srcs)} portala razlicitih vlasnickih grupa. "
                        f"Primer: {high[0]['title_a'][:160]}",
                        float(max(p["sim"] for p in high)),
                        list(srcs), today,
                    )
                    alerts_created = 1

            return {"pairs": inserted, "alerts": alerts_created}
        finally:
            await pg.close()

    result = _run_async(_run())
    logger.info("detect_copypaste zavrsen: %s", result)
    return result


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
            today = date.today()  # date objekat — asyncpg ga prima za DATE kolone; f-string daje YYYY-MM-DD
            yesterday = date.today() - timedelta(days=1)
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

            # 1. Koordinacioni alert — copy-paste iz coordination_copypaste (Faza 3, pgvector).
            # detect_copypaste task vec kreira detaljan alert; ovde dodatno hvatamo dnevni
            # zbir ako task nije stigao da kreira alert (npr. mnogo parova istog dana).
            try:
                cp = await pg.fetchrow(
                    """
                    SELECT COUNT(*) AS pair_count,
                           COUNT(DISTINCT a.source_id) + COUNT(DISTINCT b.source_id) AS src_estimate,
                           MAX(cc.similarity_score) AS max_score,
                           ARRAY_AGG(DISTINCT a.source_id) || ARRAY_AGG(DISTINCT b.source_id) AS sources
                    FROM coordination_copypaste cc
                    JOIN articles a ON a.id = cc.article_id_a
                    JOIN articles b ON b.id = cc.article_id_b
                    WHERE cc.detected_at >= NOW() - INTERVAL '24 hours'
                      AND cc.similarity_score >= $1
                      AND COALESCE(cc.same_owner_group, FALSE) = FALSE
                    """,
                    settings.COPYPASTE_ALERT_THRESHOLD,
                )
                if cp and cp["pair_count"] and cp["pair_count"] > 0:
                    srcs = sorted({s for s in (cp["sources"] or []) if s})
                    if len(srcs) >= 4:
                        await _create_alert(
                            "coordination_copy",
                            "high" if len(srcs) >= 6 else "medium",
                            f"Koordinisano kopiranje: {len(srcs)} portala",
                            f"Gotovo identičan tekst (>= {int(settings.COPYPASTE_ALERT_THRESHOLD*100)}%) "
                            f"u {cp['pair_count']} parova na {len(srcs)} portala različitih vlasničkih grupa.",
                            score=cp["max_score"],
                            source_ids=srcs,
                        )
            except Exception as exc:
                logger.warning("coordination_copy alert preskocen: %s", exc)

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
                WHERE t.today_cnt / NULLIF(b.avg_cnt, 0) >= 2.0
                  AND b.avg_cnt >= 2
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


@celery.task(name="pipeline.tasks.detect_origin")
def detect_origin(window_days: int = 7):
    """
    Origin tracking: za svaku aktivnu temu u prozoru, ko je PRVI objavio i kako se sirilo.

    Svi aktivni izvori (ukljucujuci RTS i Tanjug) imaju has_timestamp_time=TRUE od juna 2026.
    RTS dobija tacne timestamps via RSS; Tanjug via article:published_time meta tag.
    Ako je prvi clanak bez published_at (NULL), has_exact_time=FALSE i UI prikazuje ogradu.
    spread_hours se racuna samo preko clanaka sa nepraznim published_at.
    """
    logger.info("detect_origin: pocinje")

    async def _run():
        pg = await asyncpg.connect(PG_DSN)
        try:
            topics = await pg.fetch(
                f"""
                SELECT aa.primary_topic AS topic, COUNT(DISTINCT a.source_id) AS coverage
                FROM article_analysis aa JOIN articles a ON a.id = aa.article_id
                WHERE a.published_at >= NOW() - INTERVAL '{window_days} days' AND aa.primary_topic IS NOT NULL
                GROUP BY aa.primary_topic
                HAVING COUNT(DISTINCT a.source_id) >= 2
                """
            )
            created = 0
            for t in topics:
                topic = t["topic"]
                # prvi clanak (najranije objavljen) za temu u prozoru
                first = await pg.fetchrow(
                    f"""
                    SELECT a.id, a.source_id, a.published_at, COALESCE(s.has_timestamp_time, TRUE) AS exact
                    FROM articles a
                    JOIN article_analysis aa ON aa.article_id = a.id
                    JOIN sources s ON s.source_id = a.source_id
                    WHERE aa.primary_topic = $1 AND a.published_at >= NOW() - INTERVAL '{window_days} days'
                    ORDER BY a.published_at ASC
                    LIMIT 1
                    """,
                    topic,
                )
                if not first:
                    continue
                # spread samo preko exact-time izvora
                spread = await pg.fetchrow(
                    f"""
                    SELECT EXTRACT(EPOCH FROM (MAX(a.published_at) - MIN(a.published_at)))/3600.0 AS hours
                    FROM articles a
                    JOIN article_analysis aa ON aa.article_id = a.id
                    JOIN sources s ON s.source_id = a.source_id
                    WHERE aa.primary_topic = $1 AND a.published_at >= NOW() - INTERVAL '{window_days} days'
                      AND COALESCE(s.has_timestamp_time, TRUE) = TRUE
                    """,
                    topic,
                )
                narrative_id = await pg.fetchval(
                    f"""
                    SELECT an.narrative_id FROM article_narratives an
                    JOIN articles a ON a.id = an.article_id
                    JOIN article_analysis aa ON aa.article_id = a.id
                    WHERE aa.primary_topic = $1 AND a.published_at >= NOW() - INTERVAL '{window_days} days'
                    GROUP BY an.narrative_id ORDER BY COUNT(*) DESC LIMIT 1
                    """,
                    topic,
                )
                # dedup: obrisi prethodni origin za temu (rolling)
                await pg.execute("DELETE FROM origin_tracking WHERE topic = $1", topic)
                await pg.execute(
                    """INSERT INTO origin_tracking
                       (topic, first_article_id, first_source_id, first_published_at, has_exact_time,
                        total_coverage, spread_hours, narrative_id, detected_at)
                       VALUES ($1,$2,$3,$4,$5,$6,$7,$8,NOW())""",
                    topic, first["id"], first["source_id"], first["published_at"], bool(first["exact"]),
                    t["coverage"], float(spread["hours"]) if spread and spread["hours"] is not None else None,
                    narrative_id,
                )
                created += 1
            return {"topics_tracked": created}
        finally:
            await pg.close()

    result = _run_async(_run())
    logger.info("detect_origin zavrsen: %s", result)
    return result


@celery.task(name="pipeline.tasks.detect_coordination")
def detect_coordination():
    """
    Framing + narativna koordinacija. Za (tema/narativ + dan) gde >= 3 izvora dele isti
    okvir/narativ -> upis u coordination_framing / coordination_narrative (+ same_owner_group).
    Date-only izvori (RTS/Tanjug) se broje u pokrivenost ali ne uticu na vremensku tesnocu.
    Pokrece se dnevno (02:55, posle copy-paste).
    """
    logger.info("detect_coordination: pocinje")

    async def _run():
        from datetime import date
        pg = await asyncpg.connect(PG_DSN)
        try:
            today = date.today()  # date objekat — asyncpg ga prima za DATE kolone; f-string daje YYYY-MM-DD
            og = {r["source_id"]: r["owner_group"] for r in await pg.fetch("SELECT source_id, owner_group FROM sources")}

            def same_owner(srcs):
                groups = {og.get(s) for s in srcs if og.get(s)}
                return len(groups) == 1 and len(srcs) > 1

            framing_created = 0
            narrative_created = 0

            # --- Framing koordinacija: ista tema+okvir, >=3 izvora, poslednjih 24h ---
            fr_rows = await pg.fetch(
                """
                SELECT aa.primary_topic AS topic, af.framing_type_id,
                       ARRAY_AGG(DISTINCT a.source_id) AS sources,
                       AVG(af.confidence) AS avg_conf, COUNT(DISTINCT a.source_id) AS src_count
                FROM article_framings af
                JOIN articles a ON a.id = af.article_id
                JOIN article_analysis aa ON aa.article_id = a.id
                WHERE a.published_at >= NOW() - INTERVAL '24 hours' AND aa.primary_topic IS NOT NULL
                GROUP BY aa.primary_topic, af.framing_type_id
                HAVING COUNT(DISTINCT a.source_id) >= 2
                """
            )
            for r in fr_rows:
                srcs = list(r["sources"])
                so = same_owner(srcs)
                score = min(1.0, (r["src_count"] / 6.0) * float(r["avg_conf"] or 0.5) + 0.3)
                if score < settings.FRAMING_COORD_MIN_SCORE:
                    continue
                exists = await pg.fetchval(
                    "SELECT id FROM coordination_framing WHERE framing_type_id=$1 AND date=$2 LIMIT 1",
                    r["framing_type_id"], today,
                )
                if exists:
                    continue
                await pg.execute(
                    """INSERT INTO coordination_framing
                       (framing_type_id, source_ids, date, article_count, coordination_score, same_owner_group, detected_at)
                       VALUES ($1,$2,$3,$4,$5,$6,NOW())""",
                    r["framing_type_id"], srcs, today, r["src_count"], score, so,
                )
                framing_created += 1

            # --- Narativna koordinacija: isti narativ, >=3 izvora, poslednjih 48h ---
            nr_rows = await pg.fetch(
                """
                SELECT an.narrative_id, n.name,
                       ARRAY_AGG(DISTINCT a.source_id) AS sources,
                       AVG(an.confidence) AS avg_conf, COUNT(DISTINCT a.source_id) AS src_count
                FROM article_narratives an
                JOIN articles a ON a.id = an.article_id
                JOIN narratives n ON n.id = an.narrative_id
                WHERE a.published_at >= NOW() - INTERVAL '48 hours'
                GROUP BY an.narrative_id, n.name
                HAVING COUNT(DISTINCT a.source_id) >= 2
                """
            )
            for r in nr_rows:
                srcs = list(r["sources"])
                so = same_owner(srcs)
                score = min(1.0, (r["src_count"] / 6.0) * float(r["avg_conf"] or 0.5) + 0.3)
                if score < settings.NARRATIVE_COORD_MIN_SCORE:
                    continue
                exists = await pg.fetchval(
                    "SELECT id FROM coordination_narrative WHERE narrative_id=$1 AND date=$2 LIMIT 1",
                    r["narrative_id"], today,
                )
                if exists:
                    continue
                await pg.execute(
                    """INSERT INTO coordination_narrative
                       (narrative_id, source_ids, date, article_count, coordination_score, same_owner_group, detected_at)
                       VALUES ($1,$2,$3,$4,$5,$6,NOW())""",
                    r["narrative_id"], srcs, today, r["src_count"], score, so,
                )
                narrative_created += 1
                # alert za jaku cross-group narativnu koordinaciju
                if not so and score >= 0.8 and r["src_count"] >= 4:
                    ex = await pg.fetchval(
                        "SELECT id FROM alerts WHERE alert_type='narrative_coord' AND date=$1 AND title=$2 LIMIT 1",
                        today, f"Narativna koordinacija: {r['name'][:120]}",
                    )
                    if not ex:
                        await pg.execute(
                            """INSERT INTO alerts (alert_type, severity, title, description, score, source_ids, date)
                               VALUES ('narrative_coord','high',$1,$2,$3,$4,$5)""",
                            f"Narativna koordinacija: {r['name'][:120]}",
                            f"Narativ '{r['name']}' plasiran na {r['src_count']} portala različitih vlasničkih grupa u 48h.",
                            score, srcs, today,
                        )

            return {"framing_coord": framing_created, "narrative_coord": narrative_created}
        finally:
            await pg.close()

    result = _run_async(_run())
    logger.info("detect_coordination zavrsen: %s", result)
    return result


@celery.task(name="pipeline.tasks.detect_anomalies")
def detect_anomalies():
    """
    Statisticka detekcija anomalija (rolling 7d/30d baseline). Pise u `anomalies`
    + linkovan `alert` za visoka odstupanja. Dedup po (anomaly_type, topic/narrative, date).
    Pokrece se dnevno ~08:15.

    Detektori: topic_spike/drop, framing_shift, narrative_intensity, silence_anomaly.
    """
    logger.info("detect_anomalies: pocinje")

    async def _run():
        from datetime import date
        pg = await asyncpg.connect(PG_DSN)
        try:
            today = date.today()  # date objekat — asyncpg ga prima za DATE kolone; f-string daje YYYY-MM-DD
            created = 0

            # aktivni period (izborni/krizni/miran) za kontekst
            period = await pg.fetchval(
                "SELECT period_type FROM period_types WHERE $1 BETWEEN date_from AND date_to ORDER BY id DESC LIMIT 1",
                today.isoformat(),  # period_types.date_from/to su VARCHAR — poredi kao tekst (ISO sortira korektno)
            )
            period_note = f" [period: {period}]" if period else ""

            async def _save_anomaly(atype, desc, topic=None, narrative_id=None, source_id=None,
                                    baseline=None, detected=None, deviation=None, severity="medium"):
                nonlocal created
                exists = await pg.fetchval(
                    """SELECT id FROM anomalies WHERE anomaly_type=$1 AND date=$2
                       AND topic IS NOT DISTINCT FROM $3 AND narrative_id IS NOT DISTINCT FROM $4
                       AND source_id IS NOT DISTINCT FROM $5 LIMIT 1""",
                    atype, today, topic, narrative_id, source_id,
                )
                if exists:
                    return
                alert_id = None
                if severity == "high":
                    alert_exists = await pg.fetchval(
                        "SELECT id FROM alerts WHERE alert_type=$1 AND date=$2 AND title=$3 LIMIT 1",
                        "anomaly", today, desc[:200],
                    )
                    if not alert_exists:
                        alert_id = await pg.fetchval(
                            """INSERT INTO alerts (alert_type, severity, title, description, score, source_ids, date)
                               VALUES ('anomaly', $1, $2, $3, $4, $5, $6) RETURNING id""",
                            severity, desc[:200], desc + period_note,
                            float(deviation) if deviation is not None else None,
                            [source_id] if source_id else [], today,
                        )
                await pg.execute(
                    """INSERT INTO anomalies (anomaly_type, description, source_id, topic, narrative_id,
                          date, baseline_value, detected_value, deviation_pct, baseline_type, alert_id)
                       VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,'rolling_7d',$10)""",
                    atype, desc + period_note, source_id, topic, narrative_id, today,
                    baseline, detected, deviation, alert_id,
                )
                created += 1

            # 1. topic_spike / topic_drop (danas vs 7d prosek)
            topic_rows = await pg.fetch(
                """
                WITH daily AS (
                    SELECT aa.primary_topic AS topic, DATE(a.published_at) AS d, COUNT(*) AS cnt
                    FROM article_analysis aa JOIN articles a ON a.id=aa.article_id
                    WHERE a.published_at >= NOW() - INTERVAL '8 days' AND aa.primary_topic IS NOT NULL
                    GROUP BY aa.primary_topic, DATE(a.published_at)
                ),
                base AS (SELECT topic, AVG(cnt) avg_cnt FROM daily WHERE d < CURRENT_DATE GROUP BY topic),
                tod AS (SELECT topic, cnt FROM daily WHERE d = CURRENT_DATE)
                SELECT t.topic, t.cnt AS today_cnt, b.avg_cnt,
                       (t.cnt/NULLIF(b.avg_cnt,0)) AS ratio
                FROM tod t JOIN base b ON b.topic=t.topic
                WHERE b.avg_cnt >= 2
                """
            )
            for r in topic_rows:
                ratio = float(r["ratio"]) if r["ratio"] else 0
                dev = (ratio - 1) * 100
                if ratio >= 2.0:
                    await _save_anomaly("topic_spike",
                        f"Topic spike: {r['topic']} {int(dev)}% iznad 7d proseka ({r['today_cnt']} vs {r['avg_cnt']:.1f})",
                        topic=r["topic"], baseline=float(r["avg_cnt"]), detected=float(r["today_cnt"]),
                        deviation=dev, severity="high" if ratio >= 3.5 else "medium")
                elif ratio <= 0.34:
                    await _save_anomaly("topic_drop",
                        f"Topic drop: {r['topic']} {int(dev)}% ispod 7d proseka ({r['today_cnt']} vs {r['avg_cnt']:.1f})",
                        topic=r["topic"], baseline=float(r["avg_cnt"]), detected=float(r["today_cnt"]),
                        deviation=dev, severity="medium")

            # 2. framing_shift — dominantni framing za temu menja udeo > 30pp danas vs 7d
            fr_rows = await pg.fetch(
                """
                WITH today_fr AS (
                    SELECT aa.primary_topic AS topic, ft.name AS framing, COUNT(*)::float AS cnt
                    FROM article_framings af JOIN framing_types ft ON ft.id=af.framing_type_id
                    JOIN articles a ON a.id=af.article_id
                    JOIN article_analysis aa ON aa.article_id=a.id
                    WHERE DATE(a.published_at)=CURRENT_DATE AND aa.primary_topic IS NOT NULL
                    GROUP BY aa.primary_topic, ft.name
                ),
                today_tot AS (SELECT topic, SUM(cnt) tot FROM today_fr GROUP BY topic),
                base_fr AS (
                    SELECT aa.primary_topic AS topic, ft.name AS framing, COUNT(*)::float AS cnt
                    FROM article_framings af JOIN framing_types ft ON ft.id=af.framing_type_id
                    JOIN articles a ON a.id=af.article_id
                    JOIN article_analysis aa ON aa.article_id=a.id
                    WHERE a.published_at >= NOW() - INTERVAL '8 days' AND a.published_at < CURRENT_DATE
                      AND aa.primary_topic IS NOT NULL
                    GROUP BY aa.primary_topic, ft.name
                ),
                base_tot AS (SELECT topic, SUM(cnt) tot FROM base_fr GROUP BY topic)
                SELECT tf.topic, tf.framing,
                       (tf.cnt/NULLIF(tt.tot,0)) AS today_share,
                       COALESCE(bf.cnt/NULLIF(bt.tot,0),0) AS base_share,
                       tt.tot AS today_total
                FROM today_fr tf JOIN today_tot tt ON tt.topic=tf.topic
                LEFT JOIN base_fr bf ON bf.topic=tf.topic AND bf.framing=tf.framing
                LEFT JOIN base_tot bt ON bt.topic=tf.topic
                WHERE tt.tot >= 4
                """
            )
            for r in fr_rows:
                shift = (float(r["today_share"]) - float(r["base_share"])) * 100
                if shift >= 30:
                    await _save_anomaly("framing_shift",
                        f"Framing shift: '{r['framing']}' za temu {r['topic']} porastao {int(shift)}pp danas",
                        topic=r["topic"], baseline=round(float(r["base_share"]), 3),
                        detected=round(float(r["today_share"]), 3), deviation=shift, severity="medium")

            # 3. narrative_intensity — danasnji intenzitet > 150% 7d proseka
            ni_rows = await pg.fetch(
                """
                WITH agg AS (
                    SELECT narrative_id, date, SUM(intensity_score) AS day_int
                    FROM narrative_daily_intensity
                    WHERE date::date >= CURRENT_DATE - 8
                    GROUP BY narrative_id, date
                ),
                base AS (SELECT narrative_id, AVG(day_int) avg_int FROM agg WHERE date::date < CURRENT_DATE GROUP BY narrative_id),
                tod AS (SELECT narrative_id, day_int FROM agg WHERE date::date = CURRENT_DATE)
                SELECT t.narrative_id, t.day_int, b.avg_int, n.name
                FROM tod t JOIN base b ON b.narrative_id=t.narrative_id
                JOIN narratives n ON n.id=t.narrative_id
                WHERE b.avg_int > 0 AND t.day_int/NULLIF(b.avg_int,0) >= 1.5
                """
            )
            for r in ni_rows:
                dev = (float(r["day_int"]) / float(r["avg_int"]) - 1) * 100
                await _save_anomaly("narrative_intensity",
                    f"Narativ '{r['name']}' intenzitet {int(dev)}% iznad 7d proseka",
                    narrative_id=r["narrative_id"], baseline=round(float(r["avg_int"]), 2),
                    detected=round(float(r["day_int"]), 2), deviation=dev,
                    severity="high" if dev >= 200 else "medium")

            return {"anomalies_created": created, "period": period}
        finally:
            await pg.close()

    result = _run_async(_run())
    logger.info("detect_anomalies zavrsen: %s", result)
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
    Agregira neaplicirani feedback analitičara, PERSISTIRA korekcije u calibration_prompts
    (versioned, is_active) i pokrece re-analizu embedding-slicnih clanaka. Oznaci feedback
    kao applied_to_pipeline=TRUE. Pokrece se nedeljno.

    Za razliku od ranije in-memory mutacije SYSTEM_PROMPT-a, korekcije sada prezive restart
    i dele se medju workerima (build_system cita aktivne calibration_prompts iz DB).
    """
    logger.info("apply_calibration_feedback: pocinje")

    async def _run():
        pg = await asyncpg.connect(PG_DSN)
        try:
            rows = await pg.fetch(
                """
                SELECT id, article_id, analysis_type, is_correct, original_value, corrected_value, comment
                FROM calibration_feedback
                WHERE applied_to_pipeline = FALSE
                ORDER BY created_at DESC
                LIMIT 500
                """,
            )
            if not rows:
                logger.info("Nema novih feedbackova za procesiranje")
                return {"processed": 0}

            from collections import defaultdict
            groups = defaultdict(list)
            for r in rows:
                groups[r["analysis_type"]].append(dict(r))

            corrections = []
            for atype, items in groups.items():
                wrong = [i for i in items if not i["is_correct"]]
                if not wrong:
                    continue
                examples = wrong[:8]
                ex_str = "; ".join(
                    (f"'{e['original_value']}' -> '{e['corrected_value']}'"
                     if e.get("corrected_value") else f"'{e['original_value']}' (netacno)")
                    + (f" [{e['comment']}]" if e.get("comment") else "")
                    for e in examples if e.get("original_value") or e.get("comment")
                )
                if ex_str:
                    corrections.append(f"- {atype}: {len(wrong)} korekcija. Primeri: {ex_str}")

            corrections_persisted = 0
            if corrections:
                correction_note = (
                    "KOREKCIJE ANALITIČARA (na osnovu povratnih informacija — primeni pri analizi):\n"
                    + "\n".join(corrections)
                )
                # versioned upsert: deaktiviraj prethodne 'global', upisi novu verziju
                await pg.execute(
                    "UPDATE calibration_prompts SET is_active = FALSE WHERE analysis_type = 'global' AND is_active = TRUE"
                )
                next_ver = await pg.fetchval(
                    "SELECT COALESCE(MAX(version), 0) + 1 FROM calibration_prompts WHERE analysis_type = 'global'"
                )
                await pg.execute(
                    """
                    INSERT INTO calibration_prompts
                        (analysis_type, version, prompt_text, feedback_count, is_active, activated_at, created_at)
                    VALUES ('global', $1, $2, $3, TRUE, NOW(), NOW())
                    """,
                    next_ver, correction_note, len(rows),
                )
                corrections_persisted = len(corrections)
                logger.info("Persistirana kalibracija v%d (%d tipova korekcija)", next_ver, len(corrections))

            # Re-analiza: nadji embedding-slicne clanke korigovanima
            corrected_ids = [r["article_id"] for r in rows if not r["is_correct"] and r["article_id"]]
            reanalyze_ids: list[int] = []
            if corrected_ids:
                sim_rows = await pg.fetch(
                    """
                    SELECT DISTINCT e2.article_id
                    FROM article_embeddings e1
                    JOIN article_embeddings e2 ON e2.article_id <> e1.article_id
                    WHERE e1.article_id = ANY($1::bigint[])
                      AND (1 - (e1.embedding <=> e2.embedding)) >= $2
                    LIMIT $3
                    """,
                    corrected_ids, settings.CALIBRATION_SIMILARITY_THRESHOLD,
                    settings.CALIBRATION_REANALYSIS_MAX,
                )
                reanalyze_ids = [r["article_id"] for r in sim_rows]
                # ukljuci i same korigovane clanke (re-analiziraj ih pod novim promptom)
                reanalyze_ids = list(set(reanalyze_ids) | set(corrected_ids))[: settings.CALIBRATION_REANALYSIS_MAX]

            await pg.execute(
                "UPDATE calibration_feedback SET applied_to_pipeline=TRUE WHERE applied_to_pipeline=FALSE"
            )
            return {
                "processed": len(rows),
                "corrections": corrections_persisted,
                "reanalyze_queued": len(reanalyze_ids),
                "reanalyze_ids": reanalyze_ids,
            }
        finally:
            await pg.close()

    result = _run_async(_run())
    # Pokreni re-analizu van DB konekcije (zaseban task, pod novim kalibracionim promptom)
    rids = result.pop("reanalyze_ids", [])
    if rids:
        try:
            run_batch_for_articles.delay(rids)
            logger.info("Re-analiza zakazana za %d clanaka", len(rids))
        except Exception as exc:
            logger.warning("Re-analiza nije zakazana: %s", exc)
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

    target = date.fromisoformat(target_date) if target_date else date.today() - timedelta(days=1)
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
        # Persistuj u daily_summaries (istorijat — prezivljava Redis TTL)
        from pipeline.summary import persist_summary
        asyncio.get_event_loop().run_until_complete(persist_summary(summary))
        logger.info("Summary za %s generisan, sacuvan u Redis + daily_summaries", target)
        return {"status": "done", "date": target.isoformat()}

    except Exception as exc:
        logger.exception("Greska pri generisanju summary-ja: %s", exc)
        raise self.retry(exc=exc, countdown=300)
