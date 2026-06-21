import json
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc, asc, and_, or_
from typing import Optional, List

from database import get_db
from models.articles import Article
from models.sources import Source
from models.analysis import (
    ArticleAnalysis, ArticleEntity, Entity,
    ArticleFraming, FramingType, Topic, ArticleNarrative, Narrative,
    CalibrationFeedback, NarrativeProposal,
)
from api.deps import get_current_user, require_role, PaginationParams, parse_date

router = APIRouter(prefix="/articles", tags=["articles"])


def _build_article_filters(q, source_ids, date_from, date_to, topic, narrative_id,
                            political_score_min, political_score_max, has_analysis, search):
    from api.deps import parse_date
    if source_ids:
        ids = [s.strip() for s in source_ids.split(",")]
        q = q.where(Article.source_id.in_(ids))
    if date_from:
        q = q.where(Article.published_at >= parse_date(date_from))
    if date_to:
        q = q.where(Article.published_at <= parse_date(date_to))
    if search:
        q = q.where(
            or_(Article.title.ilike(f"%{search}%"), Article.text_content.ilike(f"%{search}%"))
        )
    return q


@router.get("")
async def list_articles(
    source_ids: Optional[str] = Query(default=None),
    date_from: Optional[str] = Query(default=None),
    date_to: Optional[str] = Query(default=None),
    topic: Optional[str] = Query(default=None),
    entity_id: Optional[int] = Query(default=None),
    entity_sentiment: Optional[str] = Query(default=None),  # positive|negative|neutral
    narrative_id: Optional[int] = Query(default=None),
    framing_type_id: Optional[int] = Query(default=None),
    narrative_cluster_id: Optional[int] = Query(default=None),
    political_score_min: Optional[float] = Query(default=None),
    political_score_max: Optional[float] = Query(default=None),
    has_analysis: Optional[bool] = Query(default=None),
    search: Optional[str] = Query(default=None),
    sort: str = Query(default="published_at"),
    order: str = Query(default="desc"),
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=100),
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    q = (
        select(Article, Source, ArticleAnalysis)
        .join(Source, Article.source_id == Source.source_id)
        .outerjoin(ArticleAnalysis, Article.id == ArticleAnalysis.article_id)
    )

    if source_ids:
        q = q.where(Article.source_id.in_([s.strip() for s in source_ids.split(",")]))
    if date_from:
        q = q.where(Article.published_at >= parse_date(date_from))
    if date_to:
        q = q.where(Article.published_at <= parse_date(date_to))
    if search:
        q = q.where(
            func.to_tsvector("simple", func.coalesce(Article.title, "") + " " + func.coalesce(Article.text_content, ""))
            .op("@@")(func.websearch_to_tsquery("simple", search))
        )
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
    if entity_id:
        sub = select(ArticleEntity.article_id).where(ArticleEntity.entity_id == entity_id)
        if entity_sentiment == "positive":
            sub = sub.where(ArticleEntity.sentiment > 0.2)
        elif entity_sentiment == "negative":
            sub = sub.where(ArticleEntity.sentiment < -0.2)
        elif entity_sentiment == "neutral":
            sub = sub.where(ArticleEntity.sentiment.between(-0.2, 0.2))
        q = q.where(Article.id.in_(sub))
    if narrative_id:
        sub = select(ArticleNarrative.article_id).where(ArticleNarrative.narrative_id == narrative_id)
        q = q.where(Article.id.in_(sub))
    if framing_type_id:
        sub = select(ArticleFraming.article_id).where(ArticleFraming.framing_type_id == framing_type_id)
        q = q.where(Article.id.in_(sub))
    if narrative_cluster_id:
        sub = select(NarrativeProposal.article_id).where(NarrativeProposal.cluster_id == narrative_cluster_id)
        q = q.where(Article.id.in_(sub))

    count_q = select(func.count()).select_from(q.subquery())
    total = (await db.execute(count_q)).scalar()

    sort_col = {
        "published_at": Article.published_at,
        "scraped_at": Article.scraped_at,
        "political_score": ArticleAnalysis.political_score,
        "sensationalism": ArticleAnalysis.sensationalism,
    }.get(sort, Article.published_at)

    q = q.order_by(desc(sort_col) if order == "desc" else asc(sort_col))
    q = q.offset((page - 1) * per_page).limit(per_page)

    rows = (await db.execute(q)).all()

    items = []
    for article, source, analysis in rows:
        items.append({
            "id": article.id,
            "source_id": article.source_id,
            "source_name": source.name,
            "owner_group": source.owner_group,
            "url": article.url,
            "title": article.title,
            "subtitle": article.subtitle,
            "word_count": article.word_count,
            "author": article.author,
            "published_at": article.published_at,
            "category": article.category,
            "tags": article.tags,
            "image_url": article.image_url,
            "has_analysis": analysis is not None,
            "analysis_summary": {
                "primary_topic": analysis.primary_topic,
                "political_score": analysis.political_score,
                "value_score": analysis.value_score,
                "sensationalism": analysis.sensationalism,
                "sentiment": analysis.sentiment,
            } if analysis else None,
        })

    return {
        "total": total,
        "page": page,
        "per_page": per_page,
        "pages": (total + per_page - 1) // per_page,
        "items": items,
    }


@router.get("/{article_id}")
async def get_article(
    article_id: int,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    row = (await db.execute(
        select(Article, Source, ArticleAnalysis)
        .join(Source, Article.source_id == Source.source_id)
        .outerjoin(ArticleAnalysis, Article.id == ArticleAnalysis.article_id)
        .where(Article.id == article_id)
    )).one_or_none()

    if not row:
        raise HTTPException(status_code=404, detail="NOT_FOUND")

    article, source, analysis = row

    entities = (await db.execute(
        select(ArticleEntity, Entity)
        .join(Entity, ArticleEntity.entity_id == Entity.id)
        .where(ArticleEntity.article_id == article_id)
    )).all()

    framings = (await db.execute(
        select(ArticleFraming, FramingType, Topic.key)
        .join(FramingType, ArticleFraming.framing_type_id == FramingType.id)
        .outerjoin(Topic, Topic.id == FramingType.topic_id)
        .where(ArticleFraming.article_id == article_id)
    )).all()

    narratives = (await db.execute(
        select(ArticleNarrative, Narrative)
        .join(Narrative, ArticleNarrative.narrative_id == Narrative.id)
        .where(ArticleNarrative.article_id == article_id)
    )).all()

    include_text = current_user.role in ("researcher", "admin")

    return {
        "id": article.id,
        "source_id": article.source_id,
        "source_name": source.name,
        "url": article.url,
        "title": article.title,
        "subtitle": article.subtitle,
        "text_content": article.text_content if include_text else None,
        "word_count": article.word_count,
        "author": article.author,
        "published_at": article.published_at,
        "updated_at": article.updated_at,
        "category": article.category,
        "tags": article.tags,
        "image_url": article.image_url,
        "version": article.version,
        "scraped_at": article.scraped_at,
        "has_paywall": article.has_paywall,
        "analysis": {
            "primary_topic": analysis.primary_topic,
            "topics": analysis.topics,
            "topic_confidence": analysis.topic_confidence,
            "topic_explanation": analysis.topic_explanation,
            "political_score": analysis.political_score,
            "political_explanation": analysis.political_explanation,
            "value_score": analysis.value_score,
            "value_explanation": analysis.value_explanation,
            "sensationalism": analysis.sensationalism,
            "sentiment": analysis.sentiment,
            "sentiment_score": analysis.sentiment_score,
            "analyzed_at": analysis.analyzed_at,
            "model_used": analysis.model_used,
        } if analysis else None,
        "entities": [
            {
                "id": e.id,
                "name": ent.name,
                "entity_type": ent.entity_type,
                "is_political_actor": ent.is_political_actor,
                "mention_count": e.mention_count,
                "is_quoted": e.is_quoted,
                "is_subject": e.is_subject,
            }
            for e, ent in entities
        ],
        "framings": [
            {
                "framing_type_id": f.framing_type_id,
                "framing_name": ft.name,
                "framing_description": ft.description,
                "topic_key": topic_key,  # None = globalni okvir
                "confidence": f.confidence,
                "supporting_text": f.supporting_text,
            }
            for f, ft, topic_key in framings
        ],
        "narratives": [
            {
                "narrative_id": an.narrative_id,
                "narrative_name": n.name,
                "narrative_type": n.narrative_type,
                "confidence": an.confidence,
            }
            for an, n in narratives
        ],
    }


class FeedbackRequest(BaseModel):
    analysis_type: str
    is_correct: bool
    comment: Optional[str] = None
    corrected_value: Optional[str] = None


@router.post("/{article_id}/feedback", status_code=201)
async def submit_feedback(
    article_id: int,
    req: FeedbackRequest,
    current_user=Depends(require_role("researcher", "admin")),
    db: AsyncSession = Depends(get_db),
):
    article = await db.get(Article, article_id)
    if not article:
        raise HTTPException(status_code=404, detail="NOT_FOUND")

    analysis = (await db.execute(
        select(ArticleAnalysis).where(ArticleAnalysis.article_id == article_id)
    )).scalar_one_or_none()

    original = None
    if analysis:
        original = str(getattr(analysis, req.analysis_type, None))

    feedback = CalibrationFeedback(
        user_id=current_user.id,
        article_id=article_id,
        analysis_type=req.analysis_type,
        is_correct=req.is_correct,
        comment=req.comment,
        original_value=original,
        corrected_value=req.corrected_value,
    )
    db.add(feedback)
    await db.commit()
    await db.refresh(feedback)

    return {
        "id": feedback.id,
        "applied_to_pipeline": False,
        "message": "Feedback sacuvan",
    }
