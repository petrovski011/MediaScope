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
               SUM(CASE WHEN sa.src_score > 0.2 THEN ae.mention_count ELSE 0 END) AS pro_gov_mentions,
               SUM(CASE WHEN sa.src_score < -0.2 THEN ae.mention_count ELSE 0 END) AS opp_mentions,
               SUM(CASE WHEN sa.src_score BETWEEN -0.2 AND 0.2 THEN ae.mention_count ELSE 0 END) AS neutral_mentions,
               AVG(aa.sentiment_score) AS avg_sentiment
        FROM entities e
        JOIN article_entities ae ON ae.entity_id = e.id
        JOIN articles a ON a.id = ae.article_id
        LEFT JOIN article_analysis aa ON aa.article_id = a.id
        LEFT JOIN src_align sa ON sa.source_id = a.source_id
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
                "pro_gov_mentions": int(r.pro_gov_mentions or 0),
                "opposition_mentions": int(r.opp_mentions or 0),
                "neutral_mentions": int(r.neutral_mentions or 0),
                "avg_sentiment": round(float(r.avg_sentiment), 3) if r.avg_sentiment is not None else None,
            }
            for r in rows
        ],
        "methodology_note": NOTE,
    }


@router.get("/meta-framing")
async def meta_framing(
    date_from: Optional[str] = Query(default=None),
    date_to: Optional[str] = Query(default=None),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Populisticki 'narod vs elite' meta-framing po izvoru i temi."""
    params = {}
    df = ""
    if date_from:
        df += " AND a.published_at >= :date_from"; params["date_from"] = parse_date(date_from)
    if date_to:
        df += " AND a.published_at <= :date_to"; params["date_to"] = parse_date(date_to)

    by_source = (await db.execute(text(f"""
        SELECT a.source_id,
               COUNT(*) FILTER (WHERE aa.populist_framing) AS populist,
               COUNT(*) AS total
        FROM article_analysis aa JOIN articles a ON a.id=aa.article_id
        WHERE 1=1 {df}
        GROUP BY a.source_id
        HAVING COUNT(*) FILTER (WHERE aa.populist_framing) > 0
        ORDER BY populist DESC
    """), params)).all()

    by_topic = (await db.execute(text(f"""
        SELECT aa.primary_topic AS topic,
               COUNT(*) FILTER (WHERE aa.populist_framing) AS populist,
               COUNT(*) AS total
        FROM article_analysis aa JOIN articles a ON a.id=aa.article_id
        WHERE aa.primary_topic IS NOT NULL {df}
        GROUP BY aa.primary_topic
        HAVING COUNT(*) FILTER (WHERE aa.populist_framing) > 0
        ORDER BY populist DESC
    """), params)).all()

    return {
        "by_source": [
            {"source_id": r.source_id, "populist": r.populist, "total": r.total,
             "share": round(r.populist / r.total, 3) if r.total else 0}
            for r in by_source
        ],
        "by_topic": [
            {"topic": r.topic, "populist": r.populist, "total": r.total,
             "share": round(r.populist / r.total, 3) if r.total else 0}
            for r in by_topic
        ],
        "methodology_note": NOTE,
    }
