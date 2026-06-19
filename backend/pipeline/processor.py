"""
Parsira rezultate Anthropic batch-a i upisuje u PostgreSQL.
Tabele: article_analysis, entities, article_entities
"""

import logging
from datetime import datetime, timezone
from typing import Optional

import asyncpg

from config import settings

logger = logging.getLogger(__name__)

PIPELINE_VERSION = "1.0"
PG_DSN = settings.DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")


async def process_batch_results(batch_results: list[tuple]) -> dict:
    """
    batch_results: lista (article_id, parsed_json, error) iz iter_batch_results()
    Vraca metriku: koliko upisano, gresaka, tokena.
    """
    pg = await asyncpg.connect(PG_DSN)
    try:
        return await _process(pg, batch_results)
    finally:
        await pg.close()


async def _process(pg: asyncpg.Connection, batch_results: list[tuple]) -> dict:
    metrics = {
        "saved": 0,
        "errors": 0,
        "entities_created": 0,
        "entities_linked": 0,
    }

    for article_id, parsed, error in batch_results:
        if error or not parsed:
            logger.warning("Preskacemo article %d: %s", article_id, error)
            metrics["errors"] += 1
            continue

        try:
            await _save_analysis(pg, article_id, parsed)
            metrics["saved"] += 1

            entity_stats = await _save_entities(pg, article_id, parsed.get("entities", []))
            metrics["entities_created"] += entity_stats["created"]
            metrics["entities_linked"] += entity_stats["linked"]

            await _save_framings(pg, article_id, parsed.get("framings", []))

        except Exception as e:
            logger.exception("Greska pri upisu article %d: %s", article_id, e)
            metrics["errors"] += 1

    logger.info("Batch upis zavrsen: %s", metrics)
    return metrics


async def _save_analysis(pg: asyncpg.Connection, article_id: int, data: dict) -> None:
    secondary = data.get("secondary_topics") or []
    topics_list = [data.get("primary_topic")] if data.get("primary_topic") else []
    topics_list += [t["topic"] for t in secondary if t.get("topic")]

    await pg.execute(
        """
        INSERT INTO article_analysis (
            article_id,
            topics, primary_topic, topic_confidence,
            political_score, value_score, sensationalism,
            sentiment, sentiment_score,
            topic_explanation, political_explanation, value_explanation,
            model_used, analysis_version, analyzed_at
        ) VALUES (
            $1,
            $2, $3, $4,
            $5, $6, $7,
            $8, $9,
            $10, $11, $12,
            $13, $14, $15
        )
        ON CONFLICT (article_id) DO UPDATE SET
            topics = EXCLUDED.topics,
            primary_topic = EXCLUDED.primary_topic,
            topic_confidence = EXCLUDED.topic_confidence,
            political_score = EXCLUDED.political_score,
            value_score = EXCLUDED.value_score,
            sensationalism = EXCLUDED.sensationalism,
            sentiment = EXCLUDED.sentiment,
            sentiment_score = EXCLUDED.sentiment_score,
            topic_explanation = EXCLUDED.topic_explanation,
            political_explanation = EXCLUDED.political_explanation,
            value_explanation = EXCLUDED.value_explanation,
            model_used = EXCLUDED.model_used,
            analysis_version = EXCLUDED.analysis_version,
            analyzed_at = EXCLUDED.analyzed_at
        """,
        article_id,
        topics_list,
        data.get("primary_topic"),
        data.get("primary_topic_confidence"),
        data.get("political_score"),
        data.get("value_score"),
        data.get("sensationalism"),
        data.get("sentiment"),
        data.get("sentiment_score"),
        data.get("topic_explanation"),
        data.get("political_explanation"),
        data.get("value_explanation"),
        settings.ANTHROPIC_MODEL,
        PIPELINE_VERSION,
        datetime.now(timezone.utc),
    )


async def _save_entities(
    pg: asyncpg.Connection, article_id: int, entities: list[dict]
) -> dict:
    """
    Upsert entiteta u `entities` tabelu (deduplicira po name+type),
    zatim kreira vezu u `article_entities`.
    """
    created = 0
    linked = 0

    for ent in entities[:15]:
        name = (ent.get("name") or "").strip()
        etype = (ent.get("type") or "person").lower()
        if not name:
            continue
        if etype not in ("person", "organization", "location"):
            etype = "person"

        row = await pg.fetchrow(
            "SELECT id FROM entities WHERE name = $1 AND entity_type = $2",
            name,
            etype,
        )
        if row:
            entity_id = row["id"]
        else:
            entity_id = await pg.fetchval(
                """
                INSERT INTO entities (name, entity_type, created_at, updated_at)
                VALUES ($1, $2, NOW(), NOW())
                ON CONFLICT (name, entity_type) DO UPDATE SET updated_at = NOW()
                RETURNING id
                """,
                name,
                etype,
            )
            created += 1

        try:
            await pg.execute(
                """
                INSERT INTO article_entities (
                    article_id, entity_id, mention_count, is_quoted, is_subject, context_snippet
                ) VALUES ($1, $2, $3, $4, $5, $6)
                ON CONFLICT (article_id, entity_id) DO UPDATE SET
                    mention_count = EXCLUDED.mention_count,
                    is_quoted = EXCLUDED.is_quoted,
                    is_subject = EXCLUDED.is_subject,
                    context_snippet = EXCLUDED.context_snippet
                """,
                article_id,
                entity_id,
                ent.get("mention_count") or 1,
                bool(ent.get("has_quote")),
                bool(ent.get("is_main_subject")),
                (ent.get("context") or "")[:500] or None,
            )
            linked += 1
        except Exception as e:
            logger.warning("Greska pri linkovanju entiteta %s: %s", name, e)

    return {"created": created, "linked": linked}


async def _save_framings(
    pg: asyncpg.Connection, article_id: int, framings: list[dict]
) -> None:
    for f in framings[:3]:
        framing_type = (f.get("framing_type") or "").strip()
        confidence = f.get("confidence")
        supporting_text = (f.get("supporting_text") or "")[:500] or None
        if not framing_type or confidence is None:
            continue

        type_id = await pg.fetchval(
            "SELECT id FROM framing_types WHERE name = $1", framing_type
        )
        if not type_id:
            logger.debug("Nepoznat framing_type: %s", framing_type)
            continue

        try:
            await pg.execute(
                """
                INSERT INTO article_framings (article_id, framing_type_id, confidence, supporting_text)
                VALUES ($1, $2, $3, $4)
                ON CONFLICT (article_id, framing_type_id) DO UPDATE SET
                    confidence = EXCLUDED.confidence,
                    supporting_text = EXCLUDED.supporting_text
                """,
                article_id, type_id, float(confidence), supporting_text,
            )
        except Exception as e:
            logger.warning("Greska pri upisu framinga %s za article %d: %s", framing_type, article_id, e)
