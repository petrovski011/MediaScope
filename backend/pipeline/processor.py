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


async def process_batch_results(batch_results: list[tuple], batch_id: Optional[str] = None) -> dict:
    """
    batch_results: lista (article_id, parsed_json, error) iz iter_batch_results()
    Vraca metriku: koliko upisano, gresaka, tokena.
    """
    pg = await asyncpg.connect(PG_DSN)
    try:
        return await _process(pg, batch_results, batch_id=batch_id)
    finally:
        await pg.close()


async def _log_error(pg: asyncpg.Connection, article_id: Optional[int], batch_id: Optional[str],
                     stage: str, exc) -> None:
    try:
        if isinstance(exc, str):
            err_type, err_msg = "BatchError", exc[:2000]
        else:
            err_type = type(exc).__name__
            err_msg = str(exc)[:2000]
        await pg.execute(
            "INSERT INTO processing_errors (article_id, batch_id, stage, error_type, error_message) VALUES ($1, $2, $3, $4, $5)",
            article_id, batch_id, stage, err_type, err_msg,
        )
    except Exception:
        pass  # ne smeš ovde pucati — samo logger


async def _process(pg: asyncpg.Connection, batch_results: list[tuple],
                   batch_id: Optional[str] = None) -> dict:
    metrics = {
        "saved": 0,
        "errors": 0,
        "entities_created": 0,
        "entities_linked": 0,
    }

    for article_id, parsed, error in batch_results:
        if error or not parsed:
            logger.warning("Preskacemo article %d: %s", article_id, error)
            await _log_error(pg, article_id, batch_id, "batch", error or "no_parsed_data")
            metrics["errors"] += 1
            continue

        try:
            await _save_analysis(pg, article_id, parsed)
            metrics["saved"] += 1

            entity_stats = await _save_entities(pg, article_id, parsed.get("entities", []), batch_id=batch_id)
            metrics["entities_created"] += entity_stats["created"]
            metrics["entities_linked"] += entity_stats["linked"]

            await _save_framings(pg, article_id, parsed.get("primary_topic"), parsed.get("framings", []), batch_id=batch_id)
            await _save_framing_proposals(pg, article_id, parsed.get("primary_topic"), parsed.get("new_framing_proposals", []), batch_id=batch_id)
            await _save_narratives(pg, article_id, parsed.get("narratives", []), batch_id=batch_id)
            await _save_narrative_proposals(pg, article_id, parsed.get("new_narrative_proposals", []), batch_id=batch_id)

        except Exception as e:
            logger.exception("Greska pri upisu article %d: %s", article_id, e)
            await _log_error(pg, article_id, batch_id, "processing", e)
            metrics["errors"] += 1

    logger.info("Batch upis zavrsen: %s", metrics)
    return metrics


async def _save_analysis(pg: asyncpg.Connection, article_id: int, data: dict) -> None:
    secondary = data.get("secondary_topics") or []
    topics_list = [data.get("primary_topic")] if data.get("primary_topic") else []
    topics_list += [t["topic"] for t in secondary if t.get("topic")]

    import json as _json
    propaganda_techniques = data.get("propaganda_techniques") or []
    if isinstance(propaganda_techniques, list):
        propaganda_techniques_json = _json.dumps(propaganda_techniques)
    else:
        propaganda_techniques_json = "[]"
    propaganda_targets = data.get("propaganda_targets") or []
    if isinstance(propaganda_targets, list):
        propaganda_targets_json = _json.dumps(propaganda_targets)
    else:
        propaganda_targets_json = "[]"
    geopolitical_sentiment = data.get("geopolitical_sentiment") or []
    if isinstance(geopolitical_sentiment, list):
        geopolitical_sentiment_json = _json.dumps(geopolitical_sentiment)
    else:
        geopolitical_sentiment_json = "[]"

    await pg.execute(
        """
        INSERT INTO article_analysis (
            article_id,
            topics, primary_topic, topic_confidence,
            political_score, value_score, sensationalism,
            sentiment, sentiment_score,
            topic_explanation, political_explanation, value_explanation,
            populist_framing, populist_confidence,
            propaganda_techniques, propaganda_confidence, propaganda_targets,
            geopolitical_sentiment,
            analysis_confidence,
            model_used, analysis_version, analyzed_at
        ) VALUES (
            $1,
            $2, $3, $4,
            $5, $6, $7,
            $8, $9,
            $10, $11, $12,
            $13, $14,
            $15::jsonb, $16, $17::jsonb,
            $18::jsonb,
            $19,
            $20, $21, $22
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
            populist_framing = EXCLUDED.populist_framing,
            populist_confidence = EXCLUDED.populist_confidence,
            propaganda_techniques = EXCLUDED.propaganda_techniques,
            propaganda_confidence = EXCLUDED.propaganda_confidence,
            propaganda_targets = EXCLUDED.propaganda_targets,
            geopolitical_sentiment = EXCLUDED.geopolitical_sentiment,
            analysis_confidence = EXCLUDED.analysis_confidence,
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
        bool(data.get("populist_framing")),
        data.get("populist_confidence"),
        propaganda_techniques_json,
        data.get("propaganda_confidence"),
        propaganda_targets_json,
        geopolitical_sentiment_json,
        data.get("analysis_confidence"),
        settings.ANTHROPIC_MODEL,
        PIPELINE_VERSION,
        datetime.now(timezone.utc),
    )


async def _save_entities(
    pg: asyncpg.Connection, article_id: int, entities: list[dict],
    batch_id: Optional[str] = None,
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

        is_political = bool(ent.get("is_political_actor"))
        row = await pg.fetchrow(
            "SELECT id FROM entities WHERE name = $1 AND entity_type = $2",
            name,
            etype,
        )
        if row:
            entity_id = row["id"]
            if is_political:
                # sticky-true: jednom oznacen kao politicki akter, ostaje
                await pg.execute(
                    "UPDATE entities SET is_political_actor = TRUE, updated_at = NOW() WHERE id = $1",
                    entity_id,
                )
        else:
            entity_id = await pg.fetchval(
                """
                INSERT INTO entities (name, entity_type, is_political_actor, created_at, updated_at)
                VALUES ($1, $2, $3, NOW(), NOW())
                ON CONFLICT (name, entity_type) DO UPDATE SET updated_at = NOW()
                RETURNING id
                """,
                name,
                etype,
                is_political,
            )
            created += 1

        try:
            raw_sentiment = ent.get("sentiment")
            entity_sentiment = float(raw_sentiment) if raw_sentiment is not None else None
            await pg.execute(
                """
                INSERT INTO article_entities (
                    article_id, entity_id, mention_count, is_quoted, is_subject, context_snippet, sentiment
                ) VALUES ($1, $2, $3, $4, $5, $6, $7)
                ON CONFLICT (article_id, entity_id) DO UPDATE SET
                    mention_count = EXCLUDED.mention_count,
                    is_quoted = EXCLUDED.is_quoted,
                    is_subject = EXCLUDED.is_subject,
                    context_snippet = EXCLUDED.context_snippet,
                    sentiment = EXCLUDED.sentiment
                """,
                article_id,
                entity_id,
                ent.get("mention_count") or 1,
                bool(ent.get("has_quote")),
                bool(ent.get("is_main_subject")),
                (ent.get("context") or "")[:500] or None,
                entity_sentiment,
            )
            linked += 1
        except Exception as e:
            logger.warning("Greska pri linkovanju entiteta %s: %s", name, e)
            await _log_error(pg, article_id, batch_id, "entities", e)

    return {"created": created, "linked": linked}


async def _topic_id_for_key(pg: asyncpg.Connection, topic_key: Optional[str]) -> Optional[int]:
    if not topic_key:
        return None
    # primary_topic moze biti "NOVA_TEMA: NESTO" — uzmi samo kanonski kljuc
    key = topic_key.strip()
    if key.upper().startswith("NOVA_TEMA"):
        proposed = key.split(":", 1)[-1].strip().upper().replace(" ", "_")
        if proposed:
            await pg.execute("""
                INSERT INTO topic_proposals (proposed_key, article_count, last_seen)
                VALUES ($1, 1, now())
                ON CONFLICT (proposed_key) WHERE status = 'pending'
                DO UPDATE SET article_count = topic_proposals.article_count + 1, last_seen = now()
            """, proposed)
        return None
    return await pg.fetchval("SELECT id FROM topics WHERE key = $1", key)


async def _save_framings(
    pg: asyncpg.Connection, article_id: int, primary_topic: Optional[str], framings: list[dict],
    batch_id: Optional[str] = None,
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
            await _log_error(pg, article_id, batch_id, "framings", e)


async def _save_narratives(
    pg: asyncpg.Connection, article_id: int, narratives: list[dict],
    batch_id: Optional[str] = None,
) -> None:
    """Upisuje AI mapiranje clanka na VALIDIRANE narative (po narrative_id iz kataloga)."""
    for n in (narratives or [])[: settings.MAX_NARRATIVES_PER_ARTICLE]:
        nid = n.get("narrative_id")
        confidence = n.get("confidence")
        supporting_text = (n.get("supporting_text") or "")[:500] or None
        if nid is None or confidence is None:
            continue
        try:
            nid_int = int(nid)
        except (TypeError, ValueError):
            logger.debug("Narrative_id '%s' nije validan int — preskacem", nid)
            continue
        # Mapiraj samo na postojeci, aktivan, validiran narativ (model moze pogresiti id)
        valid = await pg.fetchval(
            "SELECT id FROM narratives WHERE id = $1 AND is_active = TRUE AND is_validated = TRUE",
            nid_int,
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
                article_id, nid_int, float(confidence), supporting_text,
            )
        except Exception as e:
            logger.warning("Greska pri upisu narativa %s za article %d: %s", nid, article_id, e)
            await _log_error(pg, article_id, batch_id, "narratives", e)


async def _save_narrative_proposals(
    pg: asyncpg.Connection, article_id: int, proposals: list[dict],
    batch_id: Optional[str] = None,
) -> None:
    """Hvata AI predloge novih narativa — svaki se čuva zasebno.
    Klasterovanje po semantičkoj sličnosti radi consolidate_narrative_proposals task.
    """
    for p in (proposals or [])[:3]:
        name = (p.get("name") or "").strip()
        if not name:
            continue
        ntype = (p.get("type") or "thematic").strip().lower()
        if ntype not in ("systemic", "thematic"):
            ntype = "thematic"
        description = (p.get("description") or "")[:1000] or None
        supporting_text = (p.get("supporting_text") or "")[:500] or None

        # Ne predlažemo ako narativ već postoji u katalogu
        exists = await pg.fetchval(
            "SELECT 1 FROM narratives WHERE LOWER(name) = LOWER($1) LIMIT 1", name
        )
        if exists:
            continue
        try:
            await pg.execute(
                """
                INSERT INTO narrative_proposals
                    (name, narrative_type, description, supporting_text, article_id, status, occurrences)
                VALUES ($1, $2, $3, $4, $5, 'pending', 1)
                """,
                name, ntype, description, supporting_text, article_id,
            )
        except Exception as e:
            logger.warning("Greska pri upisu narativ predloga %s: %s", name, e)
            await _log_error(pg, article_id, batch_id, "narrative_proposals", e)


_FRAMING_COSINE_THRESHOLD = 0.22  # max cosine distance da bi se framing smatrao istim


async def _save_framing_proposals(
    pg: asyncpg.Connection, article_id: int, primary_topic: Optional[str], proposals: list[dict],
    batch_id: Optional[str] = None,
) -> None:
    """Hvata AI predloge novih framing okvira u staging (framing_type_proposals).

    Ako vec postoji pending predlog semanticki slicnog naziva/opisa (cosine < threshold)
    — inkrementira occurrences i dodaje article_id. Inace kreira novi predlog sa embeddingom.
    """
    from pipeline.embeddings import embed_texts

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

        # Generisi embedding za ovaj predlog
        try:
            embed_text = f"{name}. {description or ''}".strip()
            vecs = embed_texts([embed_text], is_query=False)
            vec_str = "[" + ",".join(f"{v:.6f}" for v in vecs[0]) + "]" if vecs else None
        except Exception as e:
            logger.warning("Embedding za framing predlog %s nije uspeo: %s", name, e)
            vec_str = None

        try:
            updated = None

            # 1. Pokusaj embedding similarity match (ako imamo embedding)
            if vec_str:
                updated = await pg.fetchval(
                    """
                    UPDATE framing_type_proposals
                    SET occurrences = occurrences + 1,
                        article_ids = CASE
                            WHEN NOT ($3 = ANY(article_ids)) THEN array_append(article_ids, $3)
                            ELSE article_ids
                        END
                    WHERE id = (
                        SELECT id FROM framing_type_proposals
                        WHERE status = 'pending'
                          AND topic_id IS NOT DISTINCT FROM $1
                          AND embedding IS NOT NULL
                          AND embedding <=> $2::vector < $4
                        ORDER BY embedding <=> $2::vector
                        LIMIT 1
                    )
                    RETURNING id
                    """,
                    topic_id, vec_str, article_id, _FRAMING_COSINE_THRESHOLD,
                )

            # 2. Fallback: exact name match (ako nema embeddinga ili nije nasao po embeddingu)
            if updated is None:
                updated = await pg.fetchval(
                    """
                    UPDATE framing_type_proposals
                    SET occurrences = occurrences + 1,
                        article_ids = CASE
                            WHEN NOT ($3 = ANY(article_ids)) THEN array_append(article_ids, $3)
                            ELSE article_ids
                        END
                    WHERE name = $1 AND status = 'pending'
                      AND topic_id IS NOT DISTINCT FROM $2
                    RETURNING id
                    """,
                    name, topic_id, article_id,
                )

            # 3. Nista nije nasao — novi predlog
            if updated is None:
                if vec_str:
                    await pg.execute(
                        """
                        INSERT INTO framing_type_proposals
                            (name, topic_id, description, supporting_text, article_id, article_ids, status, embedding)
                        VALUES ($1, $2, $3, $4, $5, ARRAY[$5], 'pending', $6::vector)
                        """,
                        name, topic_id, description, supporting_text, article_id, vec_str,
                    )
                else:
                    await pg.execute(
                        """
                        INSERT INTO framing_type_proposals
                            (name, topic_id, description, supporting_text, article_id, article_ids, status)
                        VALUES ($1, $2, $3, $4, $5, ARRAY[$5], 'pending')
                        """,
                        name, topic_id, description, supporting_text, article_id,
                    )
        except Exception as e:
            logger.warning("Greska pri upisu framing predloga %s: %s", name, e)
            await _log_error(pg, article_id, batch_id, "framing_proposals", e)
