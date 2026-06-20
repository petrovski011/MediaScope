"""
Koordinaciona analiza — identifikacija uskladjenog izvestavanja.

Tri nivoa:
1. Copy-paste — visoka trigram slicnost naslova + isti dan (>= COPYPASTE_THRESHOLD)
2. Framing koord — ista tema + isti dan + politicki skor u istom smeru + 3+ izvora
3. Similar articles — za dati clanak, pronadji slicne iz drugih izvora

Metodoloski disclaimer: koordinacija NE dokazuje nameru.
Interpretacija ostaje na istrazivacu.
"""

from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, text, and_, desc
from typing import Optional

from database import get_db
from models.articles import Article
from models.sources import Source
from models.analysis import ArticleAnalysis
from api.deps import get_current_user
from config import settings

router = APIRouter(prefix="/coordination", tags=["coordination"])

METHODOLOGY_NOTE = (
    "Koordinacija ne dokazuje nameru. "
    "Slicnost moze biti rezultat deljenja istog izvora, prenosa agencijskih vesti, "
    "ili slucajnog poklapanja. Interpretacija ostaje na istrazivacu."
)


@router.get("/copy-paste")
async def find_copy_paste_groups(
    date_from: Optional[str] = Query(default=None),
    date_to: Optional[str] = Query(default=None),
    source_ids: Optional[str] = Query(default=None),
    threshold: float = Query(default=None),
    limit: int = Query(default=30, ge=1, le=100),
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Pronalazi parove clanaka sa visokom tekstualnom slicnoscu.
    Primarno cita precomputed coordination_copypaste (pgvector cosine na lokalnim
    embeddingima — Faza 3). Ako embeddingi jos nisu generisani, pada na pg_trgm
    nad naslovima (isti dan) kao fallback.
    """
    thr = threshold or settings.COPYPASTE_THRESHOLD
    src_ids = [s.strip() for s in source_ids.split(",") if s.strip()] if source_ids else None

    # --- primarno: precomputed coordination_copypaste (embeddingi) ---
    cc_sql = """
        SELECT a.id AS a_id, a.title AS a_title, a.source_id AS a_src, a.published_at AS a_pub,
               b.id AS b_id, b.title AS b_title, b.source_id AS b_src, b.published_at AS b_pub,
               cc.similarity_score AS sim, cc.same_owner_group AS same_owner
        FROM coordination_copypaste cc
        JOIN articles a ON a.id = cc.article_id_a
        JOIN articles b ON b.id = cc.article_id_b
        WHERE cc.similarity_score >= :threshold
    """
    params = {"threshold": thr, "limit": limit}
    if date_from:
        cc_sql += " AND a.published_at >= :date_from"; params["date_from"] = date_from
    if date_to:
        cc_sql += " AND a.published_at <= :date_to"; params["date_to"] = date_to
    if src_ids:
        cc_sql += " AND (a.source_id = ANY(:srcs) OR b.source_id = ANY(:srcs))"; params["srcs"] = src_ids
    cc_sql += " ORDER BY cc.similarity_score DESC LIMIT :limit"

    rows = (await db.execute(text(cc_sql), params)).all()
    source = "embeddings"

    if not rows:
        # --- fallback: pg_trgm nad naslovima, isti dan ---
        source = "trigram_fallback"
        date_filter = ""
        if date_from:
            date_filter += " AND a1.published_at >= :date_from"
        if date_to:
            date_filter += " AND a1.published_at <= :date_to"
        source_filter = ""
        if src_ids:
            source_filter = " AND (a1.source_id = ANY(:srcs) OR a2.source_id = ANY(:srcs))"
        fb_sql = text(f"""
            SELECT a1.id AS a_id, a1.title AS a_title, a1.source_id AS a_src, a1.published_at AS a_pub,
                   a2.id AS b_id, a2.title AS b_title, a2.source_id AS b_src, a2.published_at AS b_pub,
                   similarity(a1.title, a2.title) AS sim, NULL::boolean AS same_owner
            FROM articles a1
            JOIN articles a2 ON (
                a1.id < a2.id AND a1.source_id != a2.source_id
                AND DATE(a1.published_at) = DATE(a2.published_at)
                AND similarity(a1.title, a2.title) >= :threshold
                AND length(a1.title) > 20 AND length(a2.title) > 20
            )
            WHERE 1=1 {date_filter} {source_filter}
            ORDER BY sim DESC LIMIT :limit
        """)
        rows = (await db.execute(fb_sql, params)).all()

    pairs = [
        {
            "article1": {"id": r.a_id, "title": r.a_title, "source_id": r.a_src,
                         "published_at": r.a_pub.isoformat() if r.a_pub else None},
            "article2": {"id": r.b_id, "title": r.b_title, "source_id": r.b_src,
                         "published_at": r.b_pub.isoformat() if r.b_pub else None},
            "similarity_score": round(float(r.sim), 3),
            "same_owner_group": r.same_owner,
        }
        for r in rows
    ]

    return {
        "pairs": pairs,
        "threshold_used": thr,
        "total": len(pairs),
        "source": source,
        "methodology_note": METHODOLOGY_NOTE,
    }


@router.get("/framing")
async def find_framing_coordination(
    date_from: Optional[str] = Query(default=None),
    date_to: Optional[str] = Query(default=None),
    source_ids: Optional[str] = Query(default=None),
    min_sources: int = Query(default=3, ge=2, le=20),
    limit: int = Query(default=20, ge=1, le=50),
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Pronalazi teme/dane gde 3+ izvora izvestavaju sa uskladjenim politickim skorem.
    Koordinacija = ista tema, isti dan, skor u istom smeru (svi >0.3 ili svi <-0.3).
    """
    src_ids = [s.strip() for s in source_ids.split(",") if s.strip()] if source_ids else None

    q = (
        select(
            func.date(Article.published_at).label("date"),
            ArticleAnalysis.primary_topic,
            func.count(Article.source_id.distinct()).label("source_count"),
            func.avg(ArticleAnalysis.political_score).label("avg_score"),
            func.min(ArticleAnalysis.political_score).label("min_score"),
            func.max(ArticleAnalysis.political_score).label("max_score"),
            func.array_agg(Article.source_id.distinct()).label("sources"),
        )
        .join(ArticleAnalysis, Article.id == ArticleAnalysis.article_id)
        .where(
            ArticleAnalysis.primary_topic.isnot(None),
            ArticleAnalysis.political_score.isnot(None),
        )
    )

    if src_ids:
        q = q.where(Article.source_id.in_(src_ids))
    if date_from:
        q = q.where(Article.published_at >= date_from)
    if date_to:
        q = q.where(Article.published_at <= date_to)

    q = (
        q.group_by(func.date(Article.published_at), ArticleAnalysis.primary_topic)
        .having(func.count(Article.source_id.distinct()) >= min_sources)
        .order_by(desc(func.count(Article.source_id.distinct())))
        .limit(limit)
    )

    rows = (await db.execute(q)).all()

    groups = []
    for r in rows:
        avg = float(r.avg_score) if r.avg_score else 0
        min_s = float(r.min_score) if r.min_score else 0
        max_s = float(r.max_score) if r.max_score else 0
        score_range = max_s - min_s

        # Koordinisano = mali raspon skora + svi u istom smeru
        is_coordinated = score_range < 0.4 and (
            (min_s > settings.FRAMING_COORD_MIN_SCORE - 0.7) or
            (max_s < -(settings.FRAMING_COORD_MIN_SCORE - 0.7))
        )

        groups.append({
            "date": str(r.date),
            "topic": r.primary_topic,
            "source_count": r.source_count,
            "sources": list(r.sources) if r.sources else [],
            "avg_political_score": round(avg, 3),
            "score_range": round(score_range, 3),
            "direction": "pro-vladino" if avg > 0.2 else "opoziciono" if avg < -0.2 else "neutralno",
            "coordination_signal": is_coordinated,
        })

    return {
        "groups": groups,
        "min_sources": min_sources,
        "total": len(groups),
        "methodology_note": METHODOLOGY_NOTE,
    }


@router.get("/similar/{article_id}")
async def find_similar_articles(
    article_id: int,
    limit: int = Query(default=10, ge=1, le=30),
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Za dati clanak pronalazi slicne clanke iz DRUGIH izvora.
    Primarno: pgvector cosine (semanticka slicnost, lokalni embeddingi).
    Fallback: pg_trgm nad naslovom ako clanak nema embedding.
    """
    article = await db.get(Article, article_id)
    if not article:
        raise HTTPException(status_code=404, detail="NOT_FOUND")

    has_emb = await db.scalar(text(
        "SELECT 1 FROM article_embeddings WHERE article_id = :aid AND embedding IS NOT NULL"
    ), {"aid": article_id})

    sim_thr = settings.SIMILAR_ARTICLES_THRESHOLD
    if has_emb:
        sql = text("""
            SELECT a.id, a.title, a.source_id, a.published_at, a.url,
                   1 - (e.embedding <=> q.embedding) AS sim_score,
                   aa.primary_topic, aa.political_score
            FROM article_embeddings q
            JOIN article_embeddings e ON e.article_id != q.article_id
            JOIN articles a ON a.id = e.article_id
            LEFT JOIN article_analysis aa ON aa.article_id = a.id
            WHERE q.article_id = :article_id
              AND a.source_id != :source_id
              AND (1 - (e.embedding <=> q.embedding)) >= :sim_thr
            ORDER BY e.embedding <=> q.embedding
            LIMIT :limit
        """)
        rows = (await db.execute(sql, {
            "article_id": article_id, "source_id": article.source_id,
            "sim_thr": sim_thr, "limit": limit,
        })).all()
    else:
        sql = text("""
            SELECT a.id, a.title, a.source_id, a.published_at, a.url,
                   similarity(a.title, :title) AS sim_score,
                   aa.primary_topic, aa.political_score
            FROM articles a
            LEFT JOIN article_analysis aa ON a.id = aa.article_id
            WHERE a.source_id != :source_id
              AND similarity(a.title, :title) > 0.3
              AND length(a.title) > 15
              AND a.id != :article_id
            ORDER BY sim_score DESC
            LIMIT :limit
        """)
        rows = (await db.execute(sql, {
            "title": article.title, "source_id": article.source_id,
            "article_id": article_id, "limit": limit,
        })).all()

    return {
        "article": {
            "id": article.id,
            "title": article.title,
            "source_id": article.source_id,
        },
        "similar": [
            {
                "id": r.id,
                "title": r.title,
                "source_id": r.source_id,
                "published_at": r.published_at.isoformat() if r.published_at else None,
                "url": r.url,
                "similarity_score": round(float(r.sim_score), 3),
                "primary_topic": r.primary_topic,
                "political_score": round(float(r.political_score), 3) if r.political_score else None,
            }
            for r in rows
        ],
        "methodology_note": METHODOLOGY_NOTE,
    }
