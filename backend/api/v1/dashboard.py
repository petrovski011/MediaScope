import json
from datetime import date, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc, cast, Integer
from typing import Optional

import redis as redis_lib

from database import get_db
from models.articles import Article
from models.sources import Source
from models.analysis import ArticleAnalysis, ArticleEntity, Entity
from api.deps import get_current_user
from config import settings
from pipeline.summary import REDIS_KEY

router = APIRouter(tags=["dashboard"])


def _apply_filters(q, src_ids, date_from, date_to):
    if src_ids:
        q = q.where(Article.source_id.in_(src_ids))
    if date_from:
        q = q.where(Article.published_at >= date_from)
    if date_to:
        q = q.where(Article.published_at <= date_to)
    return q


def _parse_source_ids(source_ids: Optional[str]):
    if not source_ids:
        return None
    return [s.strip() for s in source_ids.split(",") if s.strip()]


@router.get("/dashboard")
async def get_dashboard(
    source_ids: Optional[str] = Query(default=None),
    date_from: Optional[str] = Query(default=None),
    date_to: Optional[str] = Query(default=None),
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    src_ids = _parse_source_ids(source_ids)

    # Ukupno / analizirano
    total = (await db.execute(
        _apply_filters(select(func.count(Article.id)), src_ids, date_from, date_to)
    )).scalar()

    analyzed = (await db.execute(
        _apply_filters(
            select(func.count(Article.id)).join(ArticleAnalysis, Article.id == ArticleAnalysis.article_id),
            src_ids, date_from, date_to,
        )
    )).scalar()

    active_sources = (await db.execute(
        select(func.count(Source.source_id)).where(Source.is_active == True)
    )).scalar()

    # Distribucija tema
    topics_q = _apply_filters(
        select(ArticleAnalysis.primary_topic, func.count(Article.id).label("count"))
        .join(ArticleAnalysis, Article.id == ArticleAnalysis.article_id)
        .where(ArticleAnalysis.primary_topic.isnot(None))
        .group_by(ArticleAnalysis.primary_topic)
        .order_by(desc("count")),
        src_ids, date_from, date_to,
    )
    topics = [{"topic": r.primary_topic, "count": r.count} for r in (await db.execute(topics_q)).all()]

    # Politicki skor po izvoru
    political_q = _apply_filters(
        select(
            Article.source_id,
            Source.name,
            func.avg(ArticleAnalysis.political_score).label("avg_score"),
            func.avg(ArticleAnalysis.sensationalism).label("avg_sensationalism"),
            func.count(Article.id).label("count"),
        )
        .join(Source, Article.source_id == Source.source_id)
        .join(ArticleAnalysis, Article.id == ArticleAnalysis.article_id)
        .where(ArticleAnalysis.political_score.isnot(None))
        .group_by(Article.source_id, Source.name)
        .order_by(desc("avg_score")),
        src_ids, date_from, date_to,
    )
    political = [
        {
            "source_id": r.source_id,
            "name": r.name,
            "avg_score": round(r.avg_score, 3) if r.avg_score else None,
            "avg_sensationalism": round(r.avg_sensationalism, 3) if r.avg_sensationalism else None,
            "count": r.count,
        }
        for r in (await db.execute(political_q)).all()
    ]

    # Sentiment breakdown
    sentiment_q = _apply_filters(
        select(ArticleAnalysis.sentiment, func.count(Article.id).label("count"))
        .join(ArticleAnalysis, Article.id == ArticleAnalysis.article_id)
        .where(ArticleAnalysis.sentiment.isnot(None))
        .group_by(ArticleAnalysis.sentiment),
        src_ids, date_from, date_to,
    )
    sentiment = {r.sentiment: r.count for r in (await db.execute(sentiment_q)).all()}

    # Poslednji analizirani clanci
    recent_q = _apply_filters(
        select(Article, Source, ArticleAnalysis)
        .join(Source, Article.source_id == Source.source_id)
        .join(ArticleAnalysis, Article.id == ArticleAnalysis.article_id)
        .order_by(desc(ArticleAnalysis.analyzed_at))
        .limit(12),
        src_ids, date_from, date_to,
    )
    recent = [
        {
            "id": a.id,
            "title": a.title,
            "source_id": a.source_id,
            "source_name": s.name,
            "url": a.url,
            "published_at": a.published_at,
            "primary_topic": an.primary_topic,
            "political_score": an.political_score,
            "sensationalism": an.sensationalism,
            "sentiment": an.sentiment,
        }
        for a, s, an in (await db.execute(recent_q)).all()
    ]

    return {
        "stats": {
            "total": total,
            "analyzed": analyzed,
            "active_sources": active_sources,
            "pipeline_pct": round(analyzed / total * 100, 1) if total else 0,
        },
        "topics": topics,
        "political_by_source": political,
        "sentiment": sentiment,
        "recent_articles": recent,
    }


@router.get("/entities")
async def list_entities(
    source_ids: Optional[str] = Query(default=None),
    date_from: Optional[str] = Query(default=None),
    date_to: Optional[str] = Query(default=None),
    entity_type: Optional[str] = Query(default=None),
    limit: int = Query(default=30, ge=1, le=100),
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    src_ids = _parse_source_ids(source_ids)

    q = (
        select(
            Entity.id,
            Entity.name,
            Entity.entity_type,
            Entity.is_political_actor,
            func.sum(ArticleEntity.mention_count).label("total_mentions"),
            func.count(ArticleEntity.article_id.distinct()).label("article_count"),
            func.count(Article.source_id.distinct()).label("source_count"),
            func.sum(cast(ArticleEntity.is_quoted, Integer)).label("quoted_count"),
            func.sum(cast(ArticleEntity.is_subject, Integer)).label("subject_count"),
        )
        .join(ArticleEntity, Entity.id == ArticleEntity.entity_id)
        .join(Article, ArticleEntity.article_id == Article.id)
    )

    if entity_type:
        q = q.where(Entity.entity_type == entity_type)
    if src_ids:
        q = q.where(Article.source_id.in_(src_ids))
    if date_from:
        q = q.where(Article.published_at >= date_from)
    if date_to:
        q = q.where(Article.published_at <= date_to)

    q = q.group_by(Entity.id, Entity.name, Entity.entity_type, Entity.is_political_actor)
    q = q.order_by(desc("total_mentions")).limit(limit)

    rows = (await db.execute(q)).all()

    return {
        "items": [
            {
                "id": r.id,
                "name": r.name,
                "entity_type": r.entity_type,
                "is_political_actor": r.is_political_actor,
                "total_mentions": r.total_mentions or 0,
                "article_count": r.article_count or 0,
                "source_count": r.source_count or 0,
                "quoted_count": r.quoted_count or 0,
                "subject_count": r.subject_count or 0,
            }
            for r in rows
        ]
    }


@router.get("/topics/timeline")
async def topics_timeline(
    source_ids: Optional[str] = Query(default=None),
    date_from: Optional[str] = Query(default=None),
    date_to: Optional[str] = Query(default=None),
    topics: Optional[str] = Query(default=None),
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Dnevni broj clanaka po temama — za trend grafikon."""
    src_ids = _parse_source_ids(source_ids)
    topic_list = [t.strip() for t in topics.split(",")] if topics else None

    q = (
        select(
            func.date(Article.published_at).label("date"),
            ArticleAnalysis.primary_topic,
            func.count(Article.id).label("count"),
        )
        .join(ArticleAnalysis, Article.id == ArticleAnalysis.article_id)
        .where(ArticleAnalysis.primary_topic.isnot(None))
    )

    if src_ids:
        q = q.where(Article.source_id.in_(src_ids))
    if date_from:
        q = q.where(Article.published_at >= date_from)
    if date_to:
        q = q.where(Article.published_at <= date_to)
    if topic_list:
        q = q.where(ArticleAnalysis.primary_topic.in_(topic_list))

    q = q.group_by(func.date(Article.published_at), ArticleAnalysis.primary_topic)
    q = q.order_by(func.date(Article.published_at))

    rows = (await db.execute(q)).all()

    return {
        "items": [
            {"date": str(r.date), "topic": r.primary_topic, "count": r.count}
            for r in rows
        ]
    }


@router.get("/summary")
async def get_daily_summary(
    target_date: Optional[str] = Query(default=None),
    current_user=Depends(get_current_user),
):
    """
    Vraca AI-generisani dnevni pregled iz Redis cache-a.
    Ako ne postoji, vraca 404 (ne generise na zahtev — to radi Celery task).
    """
    r = redis_lib.from_url(settings.REDIS_URL, decode_responses=True)

    if target_date:
        check_dates = [target_date]
    else:
        today = date.today()
        check_dates = [today.isoformat(), (today - timedelta(days=1)).isoformat()]

    for d in check_dates:
        key = REDIS_KEY.format(date=d)
        cached = r.get(key)
        if cached:
            return json.loads(cached)

    return None


@router.get("/intraday")
async def intraday_distribution(
    date_from: Optional[str] = Query(default=None),
    date_to: Optional[str] = Query(default=None),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Distribucija clanaka po satu dana, po top temama.

    ISKLJUCUJE izvore bez tacnog vremena (RTS, Tanjug — has_timestamp_time=FALSE),
    jer im je sat nepouzdan. UI mora da prikaze ovu napomenu.
    """
    from sqlalchemy import text
    params = {}
    df = ""
    if date_from:
        df += " AND a.published_at >= :date_from"; params["date_from"] = date_from
    if date_to:
        df += " AND a.published_at <= :date_to"; params["date_to"] = date_to

    # top 6 tema
    top = (await db.execute(text(f"""
        SELECT aa.primary_topic AS topic, COUNT(*) AS c
        FROM article_analysis aa JOIN articles a ON a.id=aa.article_id
        JOIN sources s ON s.source_id=a.source_id
        WHERE COALESCE(s.has_timestamp_time, TRUE) = TRUE AND aa.primary_topic IS NOT NULL {df}
        GROUP BY aa.primary_topic ORDER BY c DESC LIMIT 6
    """), params)).all()
    top_topics = [r.topic for r in top]

    rows = (await db.execute(text(f"""
        SELECT EXTRACT(HOUR FROM a.published_at)::int AS hour, aa.primary_topic AS topic, COUNT(*) AS c
        FROM article_analysis aa JOIN articles a ON a.id=aa.article_id
        JOIN sources s ON s.source_id=a.source_id
        WHERE COALESCE(s.has_timestamp_time, TRUE) = TRUE AND aa.primary_topic IS NOT NULL {df}
        GROUP BY hour, aa.primary_topic
    """), params)).all()

    # bucket po satu
    buckets = {h: {"hour": h} for h in range(24)}
    for r in rows:
        if r.topic in top_topics:
            buckets[r.hour][r.topic] = (buckets[r.hour].get(r.topic, 0) + r.c)

    excluded = [r.source_id for r in (await db.execute(text(
        "SELECT source_id FROM sources WHERE COALESCE(has_timestamp_time, TRUE) = FALSE"
    ))).all()]

    return {
        "hourly": [buckets[h] for h in range(24)],
        "topics": top_topics,
        "intraday_note": {
            "excluded_sources": excluded,
            "reason": "RTS i Tanjug nemaju tačno vreme objave — samo datum.",
        },
    }


@router.post("/summary/generate")
async def trigger_summary_generation(
    target_date: Optional[str] = Query(default=None),
    current_user=Depends(get_current_user),
):
    """
    Manuelno pokrece generisanje summary-ja (za dev/test).
    U produkciji ovo radi Celery beat u 07:00.
    """
    from pipeline.tasks import generate_morning_summary
    result = generate_morning_summary.delay(target_date)
    return {"task_id": result.id, "status": "queued"}
