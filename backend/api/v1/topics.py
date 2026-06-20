"""Teme — pokrivenost, silence analiza, framing distribucija.

Silence analiza (sta mediji NE pokrivaju) je metodoloski jedan od najvaznijih slojeva.
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional

from api.deps import get_current_user, get_db, parse_date
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
        df += " AND a.published_at >= :date_from"; params["date_from"] = parse_date(date_from)
    if date_to:
        df += " AND a.published_at <= :date_to"; params["date_to"] = parse_date(date_to)

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


ORIGIN_NOTE = (
    "Tanjug i RTS nemaju tačno vreme objave — datum je pouzdan, sat nije. "
    "Kada je prvi izvor bez tačnog vremena, redosled unutar dana nije siguran."
)


@router.get("/{topic}/origin")
async def get_topic_origin(
    topic: str,
    window_days: int = Query(default=7, ge=1, le=30),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Origin tracking za temu: ko je prvi objavio + vremenska linija sirenja.

    spread_timeline po izvoru sa exact_time flagom (date-only izvori vidljivi ali
    oznaceni). Ne implicira kauzalni redosled kad tacno vreme nedostaje.
    """
    origin = (await db.execute(text("""
        SELECT ot.topic, ot.first_source_id, ot.first_published_at, ot.has_exact_time,
               ot.total_coverage, ot.spread_hours, ot.narrative_id
        FROM origin_tracking ot WHERE ot.topic = :topic
    """), {"topic": topic})).first()

    timeline = (await db.execute(text(f"""
        SELECT a.source_id, MIN(a.published_at) AS first_pub,
               COALESCE(s.has_timestamp_time, TRUE) AS exact_time, COUNT(*) AS article_count
        FROM articles a
        JOIN article_analysis aa ON aa.article_id = a.id
        JOIN sources s ON s.source_id = a.source_id
        WHERE aa.primary_topic = :topic AND a.published_at >= NOW() - INTERVAL '{window_days} days'
        GROUP BY a.source_id, s.has_timestamp_time
        ORDER BY first_pub ASC
    """), {"topic": topic})).all()

    return {
        "topic": topic,
        "origin": {
            "first_source_id": origin.first_source_id if origin else None,
            "first_published_at": origin.first_published_at.isoformat() if origin and origin.first_published_at else None,
            "has_exact_time": origin.has_exact_time if origin else None,
            "total_coverage": origin.total_coverage if origin else None,
            "spread_hours": round(origin.spread_hours, 1) if origin and origin.spread_hours is not None else None,
            "narrative_id": origin.narrative_id if origin else None,
        } if origin else None,
        "spread_timeline": [
            {
                "source_id": r.source_id,
                "first_published_at": r.first_pub.isoformat() if r.first_pub else None,
                "exact_time": r.exact_time,
                "article_count": r.article_count,
            }
            for r in timeline
        ],
        "origin_note": ORIGIN_NOTE,
    }
