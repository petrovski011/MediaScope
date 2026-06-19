"""
CSV export za istrazivace.
Podrzava iste filtere kao /articles endpoint.
"""

import csv
import io
from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, or_
from typing import Optional

from database import get_db
from models.articles import Article
from models.sources import Source
from models.analysis import ArticleAnalysis
from api.deps import require_role
from config import settings

router = APIRouter(prefix="/export", tags=["export"])

TOPIC_LABELS = {
    "POLITIKA": "Politika", "EU_INTEGRACIJE": "EU integracije", "KOSOVO": "Kosovo",
    "EKONOMIJA": "Ekonomija", "INFRASTRUKTURA": "Infrastruktura", "BEZBEDNOST": "Bezbednost",
    "MEDIJI_SLOBODA": "Mediji i sloboda", "PROTEST": "Protest", "KULTURA_SPORT": "Kultura/Sport",
    "HRONIKA": "Hronika", "ZDRAVLJE": "Zdravlje", "OBRAZOVANJE": "Obrazovanje",
    "SPOLJNA_POLITIKA": "Spoljna politika", "LOKALNA_VLAST": "Lokalna vlast", "DRUSTVO": "Drustvo",
}


@router.get("/articles.csv")
async def export_articles_csv(
    source_ids: Optional[str] = Query(default=None),
    date_from: Optional[str] = Query(default=None),
    date_to: Optional[str] = Query(default=None),
    topic: Optional[str] = Query(default=None),
    has_analysis: Optional[bool] = Query(default=None),
    search: Optional[str] = Query(default=None),
    political_score_min: Optional[float] = Query(default=None),
    political_score_max: Optional[float] = Query(default=None),
    current_user=Depends(require_role("researcher", "admin")),
    db: AsyncSession = Depends(get_db),
):
    q = (
        select(Article, Source, ArticleAnalysis)
        .join(Source, Article.source_id == Source.source_id)
        .outerjoin(ArticleAnalysis, Article.id == ArticleAnalysis.article_id)
    )

    if source_ids:
        ids = [s.strip() for s in source_ids.split(",") if s.strip()]
        q = q.where(Article.source_id.in_(ids))
    if date_from:
        q = q.where(Article.published_at >= date_from)
    if date_to:
        q = q.where(Article.published_at <= date_to)
    if search:
        q = q.where(or_(Article.title.ilike(f"%{search}%"), Article.text_content.ilike(f"%{search}%")))
    if topic:
        q = q.where(ArticleAnalysis.primary_topic == topic)
    if has_analysis is True:
        q = q.where(ArticleAnalysis.id.isnot(None))
    elif has_analysis is False:
        q = q.where(ArticleAnalysis.id.is_(None))
    if political_score_min is not None:
        q = q.where(ArticleAnalysis.political_score >= political_score_min)
    if political_score_max is not None:
        q = q.where(ArticleAnalysis.political_score <= political_score_max)

    q = q.order_by(desc(Article.published_at)).limit(settings.EXPORT_MAX_ROWS)

    rows = (await db.execute(q)).all()

    output = io.StringIO()
    writer = csv.writer(output, quoting=csv.QUOTE_ALL)

    writer.writerow([
        "id", "source_id", "source_name", "owner_group",
        "title", "url", "published_at", "author", "category", "word_count",
        "primary_topic", "primary_topic_label", "topic_confidence",
        "political_score", "value_score", "sensationalism",
        "sentiment", "sentiment_score", "analysis_confidence",
        "analyzed_at",
    ])

    for article, source, analysis in rows:
        writer.writerow([
            article.id,
            article.source_id,
            source.name,
            source.owner_group or "",
            article.title or "",
            article.url or "",
            article.published_at.isoformat() if article.published_at else "",
            article.author or "",
            article.category or "",
            article.word_count or "",
            analysis.primary_topic if analysis else "",
            TOPIC_LABELS.get(analysis.primary_topic, analysis.primary_topic) if analysis and analysis.primary_topic else "",
            round(analysis.topic_confidence, 3) if analysis and analysis.topic_confidence else "",
            round(analysis.political_score, 3) if analysis and analysis.political_score is not None else "",
            round(analysis.value_score, 3) if analysis and analysis.value_score is not None else "",
            round(analysis.sensationalism, 3) if analysis and analysis.sensationalism is not None else "",
            analysis.sentiment if analysis else "",
            round(analysis.sentiment_score, 3) if analysis and analysis.sentiment_score is not None else "",
            round(analysis.analysis_confidence, 3) if analysis and getattr(analysis, "analysis_confidence", None) else "",
            analysis.analyzed_at.isoformat() if analysis and analysis.analyzed_at else "",
        ])

    csv_bytes = output.getvalue().encode("utf-8-sig")  # utf-8-sig za Excel kompatibilnost

    return Response(
        content=csv_bytes,
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": "attachment; filename=mediascope_export.csv",
            "X-Row-Count": str(len(rows)),
        },
    )
