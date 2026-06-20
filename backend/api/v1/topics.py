"""Teme — pokrivenost, silence analiza, framing distribucija.

Silence analiza (sta mediji NE pokrivaju) je metodoloski jedan od najvaznijih slojeva.
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional

from api.deps import get_current_user, get_db
from services.analytics_service import (
    topic_coverage, topic_framing_split, METHODOLOGY_SILENCE_NOTE,
)

router = APIRouter(prefix="/topics", tags=["topics"])


@router.get("")
async def list_topics(
    date_from: Optional[str] = Query(default=None),
    date_to: Optional[str] = Query(default=None),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Lista tema sa brojem clanaka i brojem izvora koji ih pokrivaju."""
    params = {}
    df = ""
    if date_from:
        df += " AND a.published_at >= :date_from"; params["date_from"] = date_from
    if date_to:
        df += " AND a.published_at <= :date_to"; params["date_to"] = date_to

    rows = (await db.execute(text(f"""
        SELECT aa.primary_topic AS topic,
               COUNT(*) AS article_count,
               COUNT(DISTINCT a.source_id) AS source_count,
               AVG(aa.political_score) AS avg_political
        FROM article_analysis aa
        JOIN articles a ON a.id = aa.article_id
        WHERE aa.primary_topic IS NOT NULL {df}
        GROUP BY aa.primary_topic
        ORDER BY article_count DESC
    """), params)).all()

    total_sources = (await db.execute(text(
        "SELECT COUNT(*) FROM sources WHERE is_active = TRUE"
    ))).scalar() or 0

    return {
        "topics": [
            {
                "topic": r.topic,
                "article_count": r.article_count,
                "source_count": r.source_count,
                "silent_source_count": max(0, total_sources - r.source_count),
                "avg_political": round(float(r.avg_political), 3) if r.avg_political is not None else None,
            }
            for r in rows
        ],
        "total_sources": total_sources,
    }


@router.get("/{topic}/coverage")
async def get_topic_coverage(
    topic: str,
    date_from: Optional[str] = Query(default=None),
    date_to: Optional[str] = Query(default=None),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    result = await topic_coverage(db, topic, date_from, date_to)
    result["silence_note"] = METHODOLOGY_SILENCE_NOTE
    return result


@router.get("/{topic}/framing")
async def get_topic_framing(
    topic: str,
    date_from: Optional[str] = Query(default=None),
    date_to: Optional[str] = Query(default=None),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    return await topic_framing_split(db, topic, date_from, date_to)
