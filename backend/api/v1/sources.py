from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc, text
from typing import Optional, List

from database import get_db
from models.sources import Source
from models.articles import Article, ScraperRun
from models.analysis import ArticleAnalysis
from api.deps import get_current_user, parse_date

router = APIRouter(prefix="/sources", tags=["sources"])


@router.get("/comparison")
async def sources_comparison(
    source_ids: str = Query(..., description="comma-separated source ids"),
    metric: str = Query(default="political_score"),
    days: int = Query(default=30, ge=7, le=180),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Vremenska serija (dnevni prosek) izabrane metrike za vise izvora — za poredjenje."""
    col = {
        "political_score": "aa.political_score",
        "sensationalism": "aa.sensationalism",
        "value_score": "aa.value_score",
    }.get(metric, "aa.political_score")
    srcs = [s.strip() for s in source_ids.split(",") if s.strip()]
    if not srcs:
        return {"metric": metric, "sources": [], "series": []}

    rows = (await db.execute(text(f"""
        SELECT a.source_id, DATE(a.published_at) AS day, AVG({col}) AS val
        FROM articles a JOIN article_analysis aa ON aa.article_id = a.id
        WHERE a.source_id = ANY(:srcs) AND a.published_at >= NOW() - INTERVAL '{days} days'
          AND {col} IS NOT NULL
        GROUP BY a.source_id, DATE(a.published_at)
        ORDER BY day
    """), {"srcs": srcs})).all()

    by_day: dict = {}
    for r in rows:
        d = r.day.isoformat()
        by_day.setdefault(d, {"date": d})[r.source_id] = round(float(r.val), 3)
    return {"metric": metric, "sources": srcs, "series": [by_day[d] for d in sorted(by_day)]}


@router.get("")
async def list_sources(
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    sources = (await db.execute(select(Source).order_by(Source.name))).scalars().all()

    result = []
    for s in sources:
        stats_q = await db.execute(
            select(
                func.count(Article.id).label("total"),
                func.max(Article.scraped_at).label("last_scraped"),
            ).where(Article.source_id == s.source_id)
        )
        stats = stats_q.one()

        today_count = (await db.execute(
            select(func.count(Article.id)).where(
                Article.source_id == s.source_id,
                func.date(Article.scraped_at) == func.current_date(),
            )
        )).scalar()

        avg_q = await db.execute(
            select(
                func.avg(ArticleAnalysis.political_score),
                func.avg(ArticleAnalysis.value_score),
                func.avg(ArticleAnalysis.sensationalism),
            ).join(Article, ArticleAnalysis.article_id == Article.id)
            .where(Article.source_id == s.source_id)
        )
        avgs = avg_q.one()

        result.append({
            "source_id": s.source_id,
            "name": s.name,
            "url": s.url,
            "owner": s.owner,
            "owner_group": s.owner_group,
            "media_type": s.media_type,
            "is_active": s.is_active,
            "has_timestamp_time": s.has_timestamp_time,
            "has_author": s.has_author,
            "stats": {
                "articles_total": stats.total or 0,
                "articles_today": today_count or 0,
                "last_scraped": stats.last_scraped,
                "avg_political_score": round(avgs[0], 3) if avgs[0] else None,
                "avg_value_score": round(avgs[1], 3) if avgs[1] else None,
                "avg_sensationalism": round(avgs[2], 3) if avgs[2] else None,
            },
        })

    return {"items": result}


@router.get("/{source_id}")
async def get_source(
    source_id: str,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    source = (await db.execute(
        select(Source).where(Source.source_id == source_id)
    )).scalar_one_or_none()

    if not source:
        raise HTTPException(status_code=404, detail="NOT_FOUND")

    # Score history — last 30 days
    history_q = await db.execute(
        select(
            func.date(Article.published_at).label("date"),
            func.avg(ArticleAnalysis.political_score).label("political_score"),
            func.avg(ArticleAnalysis.sensationalism).label("sensationalism"),
            func.count(Article.id).label("article_count"),
        )
        .join(ArticleAnalysis, Article.id == ArticleAnalysis.article_id)
        .where(Article.source_id == source_id)
        .group_by(func.date(Article.published_at))
        .order_by(desc(func.date(Article.published_at)))
        .limit(30)
    )
    history = [
        {
            "date": str(r.date),
            "political_score": round(r.political_score, 3) if r.political_score else None,
            "sensationalism": round(r.sensationalism, 3) if r.sensationalism else None,
            "article_count": r.article_count,
        }
        for r in history_q.all()
    ]

    return {
        "source_id": source.source_id,
        "name": source.name,
        "url": source.url,
        "owner": source.owner,
        "owner_group": source.owner_group,
        "media_type": source.media_type,
        "scraper_method": source.scraper_method,
        "is_active": source.is_active,
        "has_timestamp_time": source.has_timestamp_time,
        "has_author": source.has_author,
        "has_category": source.has_category,
        "cloudflare": source.cloudflare,
        "notes": source.notes,
        "score_history": list(reversed(history)),
    }
