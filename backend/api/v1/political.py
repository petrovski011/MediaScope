"""Politicka analiza — narativni akteri + meta-framing (narod vs elite).

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


@router.get("/actors")
async def political_actors(
    date_from: Optional[str] = Query(default=None),
    date_to: Optional[str] = Query(default=None),
    limit: int = Query(default=40, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Politicki akteri: pominjanja + prosecan politicki skor clanaka koji ih pominju,
    podeljeno po alignment-u izvora (pro-vlada / opozicija / neutralno).

    Alignment izvora se izvodi iz proseka political_score po izvoru.
    """
    params = {"limit": limit}
    df = ""
    if date_from:
        df += " AND a.published_at >= :date_from"; params["date_from"] = parse_date(date_from)
    if date_to:
        df += " AND a.published_at <= :date_to"; params["date_to"] = parse_date(date_to)

    rows = (await db.execute(text(f"""
        WITH src_align AS (
            SELECT a.source_id, AVG(aa.political_score) AS src_score
            FROM articles a JOIN article_analysis aa ON aa.article_id=a.id
            WHERE aa.political_score IS NOT NULL
            GROUP BY a.source_id
        )
        SELECT e.id, e.name, e.entity_type,
               COUNT(ae.id) AS mentions,
               COUNT(DISTINCT a.source_id) AS source_count,
               SUM(CASE WHEN ae.sentiment > 0.2 THEN ae.mention_count ELSE 0 END) AS positive_mentions,
               SUM(CASE WHEN ae.sentiment < -0.2 THEN ae.mention_count ELSE 0 END) AS negative_mentions,
               SUM(CASE WHEN ae.sentiment BETWEEN -0.2 AND 0.2 THEN ae.mention_count ELSE 0 END) AS neutral_mentions,
               AVG(ae.sentiment) AS avg_entity_sentiment
        FROM entities e
        JOIN article_entities ae ON ae.entity_id = e.id
        JOIN articles a ON a.id = ae.article_id
        WHERE e.is_political_actor = TRUE {df}
        GROUP BY e.id, e.name, e.entity_type
        ORDER BY mentions DESC
        LIMIT :limit
    """), params)).all()

    return {
        "actors": [
            {
                "id": r.id, "name": r.name, "entity_type": r.entity_type,
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
    return {"by_technique": by_technique, "by_source": by_source, "methodology_note": NOTE}
