"""Politicka analiza — narativni akteri + propaganda.

Metodologija: politicki akteri se identifikuju kroz NER iz medijskog sadrzaja.
Korelacija ne dokazuje da je medij svesni instrument — interpretacija na istrazivacu.
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional

from api.deps import get_current_user, get_db, parse_date

router = APIRouter(prefix="/political", tags=["political"])

NOTE = ("Politička analiza koristi NER iz medijskog sadržaja. Korelacija ne dokazuje nameru — "
        "interpretacija ostaje na istraživaču.")


def _parse_source_ids(source_ids: Optional[str]):
    if not source_ids:
        return None
    return [s.strip() for s in source_ids.split(",") if s.strip()]


@router.get("/actors")
async def political_actors(
    date_from: Optional[str] = Query(default=None),
    date_to: Optional[str] = Query(default=None),
    source_ids: Optional[str] = Query(default=None),
    limit: int = Query(default=40, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Politicki akteri: pominjanja + sentiment u kom se akter pominje, filtrirano
    po datumu i izabranim medijima. Sentiment je per-akter (article_entities.sentiment),
    ne sentiment celog teksta.
    """
    params = {"limit": limit}
    df = ""
    if date_from:
        df += " AND a.published_at >= :date_from"; params["date_from"] = parse_date(date_from)
    if date_to:
        df += " AND a.published_at <= :date_to"; params["date_to"] = parse_date(date_to)
    src_ids = _parse_source_ids(source_ids)
    if src_ids:
        df += " AND a.source_id = ANY(:source_ids)"; params["source_ids"] = src_ids

    rows = (await db.execute(text(f"""
        SELECT
            COALESCE(canon.id, e.id)          AS eff_id,
            COALESCE(canon.name, e.name)       AS name,
            COALESCE(canon.entity_type, e.entity_type) AS entity_type,
            COUNT(ae.id)                       AS mentions,
            COUNT(DISTINCT a.source_id)        AS source_count,
            SUM(CASE WHEN ae.sentiment >  0.2 THEN ae.mention_count ELSE 0 END) AS positive_mentions,
            SUM(CASE WHEN ae.sentiment < -0.2 THEN ae.mention_count ELSE 0 END) AS negative_mentions,
            SUM(CASE WHEN ae.sentiment BETWEEN -0.2 AND 0.2 THEN ae.mention_count ELSE 0 END) AS neutral_mentions,
            AVG(ae.sentiment)                  AS avg_entity_sentiment
        FROM entities e
        LEFT JOIN entities canon ON canon.id = e.canonical_id
        JOIN article_entities ae ON ae.entity_id = e.id
        JOIN articles a ON a.id = ae.article_id
        WHERE (e.is_political_actor = TRUE OR canon.is_political_actor = TRUE) {df}
        GROUP BY COALESCE(canon.id, e.id), COALESCE(canon.name, e.name), COALESCE(canon.entity_type, e.entity_type)
        ORDER BY mentions DESC
        LIMIT :limit
    """), params)).all()

    return {
        "actors": [
            {
                "id": r.eff_id, "name": r.name, "entity_type": r.entity_type,
                "mentions": r.mentions, "source_count": r.source_count,
                "positive_mentions": int(r.positive_mentions or 0),
                "negative_mentions": int(r.negative_mentions or 0),
                "neutral_mentions": int(r.neutral_mentions or 0),
                "avg_entity_sentiment": round(float(r.avg_entity_sentiment), 3) if r.avg_entity_sentiment is not None else None,
            }
            for r in rows
        ],
        "methodology_note": NOTE,
    }


@router.get("/propaganda")
async def propaganda_stats(
    date_from: Optional[str] = Query(default=None),
    date_to: Optional[str] = Query(default=None),
    source_ids: Optional[str] = Query(default=None),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Agregatni pregled propagandnih tehnika po izvoru i tehnici."""
    import json as _json
    params = {}
    df = ""
    if date_from:
        df += " AND a.published_at >= :date_from"; params["date_from"] = parse_date(date_from)
    if date_to:
        df += " AND a.published_at <= :date_to"; params["date_to"] = parse_date(date_to)
    src_ids = _parse_source_ids(source_ids)
    if src_ids:
        df += " AND a.source_id = ANY(:source_ids)"; params["source_ids"] = src_ids

    rows = (await db.execute(text(f"""
        SELECT a.source_id, aa.propaganda_techniques, COUNT(*) AS article_count
        FROM article_analysis aa
        JOIN articles a ON a.id = aa.article_id
        WHERE aa.propaganda_techniques IS NOT NULL
          AND jsonb_array_length(aa.propaganda_techniques) > 0 {df}
        GROUP BY a.source_id, aa.propaganda_techniques
        ORDER BY article_count DESC
        LIMIT 500
    """), params)).all()

    technique_counts: dict = {}
    source_technique: dict = {}
    for r in rows:
        techs = r.propaganda_techniques or []
        if isinstance(techs, str):
            techs = _json.loads(techs)
        src = r.source_id
        cnt = int(r.article_count)
        for t in techs:
            technique_counts[t] = technique_counts.get(t, 0) + cnt
            if src not in source_technique:
                source_technique[src] = {}
            source_technique[src][t] = source_technique[src].get(t, 0) + cnt

    by_technique = sorted(
        [{"technique": k, "count": v} for k, v in technique_counts.items()],
        key=lambda x: -x["count"]
    )
    by_source = [
        {"source_id": src, "techniques": techs, "total": sum(techs.values())}
        for src, techs in sorted(source_technique.items(), key=lambda x: -sum(x[1].values()))
    ]

    # Smear kampanje po target_group
    target_rows = (await db.execute(text(f"""
        SELECT elem->>'target_group' AS target_group, COUNT(*) AS cnt
        FROM article_analysis aa
        JOIN articles a ON a.id = aa.article_id
        CROSS JOIN jsonb_array_elements(aa.propaganda_targets) AS elem
        WHERE aa.propaganda_targets IS NOT NULL
          AND jsonb_array_length(aa.propaganda_targets) > 0 {df}
        GROUP BY target_group
        ORDER BY cnt DESC
    """), params)).all()
    by_target_group = [{"target_group": r.target_group, "count": int(r.cnt)} for r in target_rows if r.target_group]

    return {"by_technique": by_technique, "by_source": by_source, "by_target_group": by_target_group, "methodology_note": NOTE}


@router.get("/geopolitical")
async def geopolitical_sentiment(
    date_from: Optional[str] = Query(default=None),
    date_to: Optional[str] = Query(default=None),
    source_ids: Optional[str] = Query(default=None),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Prosečan geopolitički sentiment po akteru (EU, Rusija, SAD, Kina, NATO, Zapad).

    Vraća kako srpski mediji prikazuju geopolitičke aktere u izabranom periodu/filteru.
    Sentiment: -1.0 (izrazito negativan tretman) do +1.0 (izrazito pozitivan tretman).
    """
    params = {}
    df = ""
    if date_from:
        df += " AND a.published_at >= :date_from"; params["date_from"] = parse_date(date_from)
    if date_to:
        df += " AND a.published_at <= :date_to"; params["date_to"] = parse_date(date_to)
    src_ids = _parse_source_ids(source_ids)
    if src_ids:
        df += " AND a.source_id = ANY(:source_ids)"; params["source_ids"] = src_ids

    rows = (await db.execute(text(f"""
        SELECT
            elem->>'actor' AS actor,
            ROUND(AVG((elem->>'sentiment')::float)::numeric, 3) AS avg_sentiment,
            COUNT(*) AS article_count
        FROM article_analysis aa
        JOIN articles a ON a.id = aa.article_id
        CROSS JOIN jsonb_array_elements(aa.geopolitical_sentiment) AS elem
        WHERE aa.geopolitical_sentiment IS NOT NULL
          AND jsonb_array_length(aa.geopolitical_sentiment) > 0 {df}
        GROUP BY actor
        ORDER BY avg_sentiment DESC
    """), params)).all()

    # Per-source per-actor breakdown
    by_source_rows = (await db.execute(text(f"""
        SELECT
            a.source_id,
            elem->>'actor' AS actor,
            ROUND(AVG((elem->>'sentiment')::float)::numeric, 3) AS avg_sentiment,
            COUNT(*) AS cnt
        FROM article_analysis aa
        JOIN articles a ON a.id = aa.article_id
        CROSS JOIN jsonb_array_elements(aa.geopolitical_sentiment) AS elem
        WHERE aa.geopolitical_sentiment IS NOT NULL
          AND jsonb_array_length(aa.geopolitical_sentiment) > 0 {df}
        GROUP BY a.source_id, actor
        ORDER BY a.source_id, actor
    """), params)).all()

    by_source: dict = {}
    for r in by_source_rows:
        if r.source_id not in by_source:
            by_source[r.source_id] = {}
        by_source[r.source_id][r.actor] = float(r.avg_sentiment)

    return {
        "by_actor": [
            {
                "actor": r.actor,
                "avg_sentiment": float(r.avg_sentiment),
                "article_count": int(r.article_count),
            }
            for r in rows if r.actor
        ],
        "by_source": [
            {"source_id": src, "actors": actors}
            for src, actors in sorted(by_source.items())
        ],
        "methodology_note": "Sentiment: -1.0 = izrazito negativan tretman akteru, +1.0 = izrazito pozitivan. Meri se tretman u tekstu, ne opšti stav uredništva.",
    }
