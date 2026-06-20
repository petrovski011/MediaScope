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

            await _save_framings(pg, article_id, parsed.get("primary_topic"), parsed.get("framings", []))
            await _save_framing_proposals(pg, article_id, parsed.get("primary_topic"), parsed.get("new_framing_proposals", []))
            await _save_narratives(pg, article_id, parsed.get("narratives", []))
            await _save_narrative_proposals(pg, article_id, parsed.get("new_narrative_proposals", []))

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


async def _topic_id_for_key(pg: asyncpg.Connection, topic_key: Optional[str]) -> Optional[int]:
    if not topic_key:
        return None
    # primary_topic moze biti "NOVA_TEMA: NESTO" — uzmi samo kanonski kljuc
    key = topic_key.strip()
    if key.upper().startswith("NOVA_TEMA"):
        return None
    return await pg.fetchval("SELECT id FROM topics WHERE key = $1", key)


async def _save_framings(
    pg: asyncpg.Connection, article_id: int, primary_topic: Optional[str], framings: list[dict]
) -> None:
    """Upisuje framinge resolucijom po (name, topic_id).

    Globalni okviri (topic_id NULL) vaze uvek; tematski okviri se vezuju za temu clanka.
    """
    topic_id = await _topic_id_for_key(pg, primary_topic)

    for f in framings[: settings.MAX_FRAMINGS_PER_ARTICLE]:
        framing_type = (f.get("framing_type") or "").strip()
        confidence = f.get("confidence")
        supporting_text = (f.get("supporting_text") or "")[:500] or None
        if not framing_type or confidence is None:
            continue

        # Prvo probaj tematski okvir za temu clanka, pa globalni (topic_id NULL).
        type_id = None
        if topic_id is not None:
            type_id = await pg.fetchval(
                "SELECT id FROM framing_types WHERE name = $1 AND topic_id = $2",
                framing_type, topic_id,
            )
        if type_id is None:
            type_id = await pg.fetchval(
                "SELECT id FROM framing_types WHERE name = $1 AND topic_id IS NULL",
                framing_type,
            )
        if type_id is None:
            # Naziv postoji ali za drugu temu — preskoci (metodologija: tematski je striktan)
            logger.debug("Framing '%s' nije validan za temu '%s'", framing_type, primary_topic)
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


async def _save_narratives(
    pg: asyncpg.Connection, article_id: int, narratives: list[dict]
) -> None:
    """Upisuje AI mapiranje clanka na VALIDIRANE narative (po narrative_id iz kataloga)."""
    for n in (narratives or [])[: settings.MAX_NARRATIVES_PER_ARTICLE]:
        nid = n.get("narrative_id")
        confidence = n.get("confidence")
        supporting_text = (n.get("supporting_text") or "")[:500] or None
        if nid is None or confidence is None:
            continue
        # Mapiraj samo na postojeci, aktivan, validiran narativ (model moze pogresiti id)
        valid = await pg.fetchval(
            "SELECT id FROM narratives WHERE id = $1 AND is_active = TRUE AND is_validated = TRUE",
            int(nid),
        )
        if not valid:
            logger.debug("Narrative_id %s nije validan/aktivan — preskacem", nid)
            continue
        try:
            await pg.execute(
                """
                INSERT INTO article_narratives (article_id, narrative_id, confidence, supporting_text)
                VALUES ($1, $2, $3, $4)
                ON CONFLICT (article_id, narrative_id) DO UPDATE SET
                    confidence = EXCLUDED.confidence,
                    supporting_text = EXCLUDED.supporting_text
                """,
                article_id, int(nid), float(confidence), supporting_text,
            )
        except Exception as e:
            logger.warning("Greska pri upisu narativa %s za article %d: %s", nid, article_id, e)


async def _save_narrative_proposals(
    pg: asyncpg.Connection, article_id: int, proposals: list[dict]
) -> None:
    """Hvata AI predloge novih narativa u staging (narrative_proposals), dedup po imenu."""
    for p in (proposals or [])[:3]:
        name = (p.get("name") or "").strip()
        if not name:
            continue
        ntype = (p.get("type") or "thematic").strip().lower()
        if ntype not in ("systemic", "thematic"):
            ntype = "thematic"
        description = (p.get("description") or "")[:1000] or None
        supporting_text = (p.get("supporting_text") or "")[:500] or None

        # Ako narativ vec postoji (po imenu) — nije predlog
        exists = await pg.fetchval("SELECT 1 FROM narratives WHERE LOWER(name) = LOWER($1) LIMIT 1", name)
        if exists:
            continue
        try:
            updated = await pg.fetchval(
                """
                UPDATE narrative_proposals SET occurrences = occurrences + 1
                WHERE LOWER(name) = LOWER($1) AND status = 'pending'
                RETURNING id
                """,
                name,
            )
            if updated is None:
                await pg.execute(
                    """
                    INSERT INTO narrative_proposals
                        (name, narrative_type, description, supporting_text, article_id, status)
                    VALUES ($1, $2, $3, $4, $5, 'pending')
                    """,
                    name, ntype, description, supporting_text, article_id,
                )
        except Exception as e:
            logger.warning("Greska pri upisu narativ predloga %s: %s", name, e)


async def _save_framing_proposals(
    pg: asyncpg.Connection, article_id: int, primary_topic: Optional[str], proposals: list[dict]
) -> None:
    """Hvata AI predloge novih framing okvira u staging (framing_type_proposals).

    Ako vec postoji pending predlog istog imena/teme — inkrementira occurrences.
    """
    topic_id = await _topic_id_for_key(pg, primary_topic)

    for p in (proposals or [])[:3]:
        name = (p.get("name") or "").strip()
        if not name:
            continue
        description = (p.get("description") or "")[:500] or None
        supporting_text = (p.get("supporting_text") or "")[:500] or None

        # Ako okvir vec postoji u framing_types (globalni ili za istu temu) — nije predlog.
        exists = await pg.fetchval(
            "SELECT 1 FROM framing_types WHERE name = $1 AND (topic_id = $2 OR topic_id IS NULL) LIMIT 1",
            name, topic_id,
        )
        if exists:
            continue

        try:
            updated = await pg.fetchval(
                """
                UPDATE framing_type_proposals
                SET occurrences = occurrences + 1
                WHERE name = $1 AND status = 'pending'
                  AND topic_id IS NOT DISTINCT FROM $2
                RETURNING id
                """,
                name, topic_id,
            )
            if updated is None:
                await pg.execute(
                    """
                    INSERT INTO framing_type_proposals
                        (name, topic_id, description, supporting_text, article_id, status)
                    VALUES ($1, $2, $3, $4, $5, 'pending')
                    """,
                    name, topic_id, description, supporting_text, article_id,
                )
        except Exception as e:
            logger.warning("Greska pri upisu framing predloga %s: %s", name, e)
