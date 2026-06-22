"""Teme — pokrivenost, silence analiza, framing distribucija.

Silence analiza (sta mediji NE pokrivaju) je metodoloski jedan od najvaznijih slojeva.
"""
from fastapi import APIRouter, Depends, Query, HTTPException
from pydantic import BaseModel
from sqlalchemy import text, select, desc
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional

from api.deps import get_current_user, require_role, get_db, parse_date
from api.v1.researcher_log import log_action
from models.analysis import TopicProposal, Topic
from services.analytics_service import (
    topic_coverage, topic_framing_split, METHODOLOGY_SILENCE_NOTE,
)

router = APIRouter(prefix="/topics", tags=["topics"])


@router.get("")
async def list_topics(
    date_from: Optional[str] = Query(default=None),
    date_to: Optional[str] = Query(default=None),
    source_ids: Optional[str] = Query(default=None),
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
    src_ids = [s.strip() for s in source_ids.split(",") if s.strip()] if source_ids else None
    if src_ids:
        df += " AND a.source_id = ANY(:source_ids)"; params["source_ids"] = src_ids

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

    # Kad je aktivan source filter, silence se računa u odnosu na izabrane izvore.
    if src_ids:
        total_sources = len(src_ids)
    else:
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
    "Stariji arhivski članci (pre juna 2026.) nemaju published_at — isključeni su iz ove analize. "
    "Redosled unutar dana je pouzdan samo za članke sa tačnim timestampom."
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


# ─── Topic proposals (NOVA_TEMA iz pipeline-a) ───────────────────────────────

class AcceptProposalRequest(BaseModel):
    label_sr: str


@router.get("/proposals")
async def list_topic_proposals(
    status: str = Query(default="pending"),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    rows = (await db.execute(
        select(TopicProposal)
        .where(TopicProposal.status == status, TopicProposal.article_count >= 3)
        .order_by(desc(TopicProposal.article_count))
    )).scalars().all()
    return {
        "proposals": [
            {
                "id": r.id, "key": r.proposed_key, "count": r.article_count,
                "first_seen": r.first_seen.isoformat() if r.first_seen else None,
                "last_seen": r.last_seen.isoformat() if r.last_seen else None,
                "status": r.status,
            }
            for r in rows
        ]
    }


@router.post("/proposals/{proposal_id}/accept")
async def accept_topic_proposal(
    proposal_id: int,
    body: AcceptProposalRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role("researcher", "admin")),
):
    proposal = await db.get(TopicProposal, proposal_id)
    if not proposal:
        raise HTTPException(status_code=404, detail="Predlog nije pronađen")
    if proposal.status != "pending":
        raise HTTPException(status_code=400, detail="Predlog nije u statusu 'pending'")

    # Proveri da li tema već postoji
    existing = (await db.execute(
        select(Topic).where(Topic.key == proposal.proposed_key)
    )).scalar_one_or_none()

    if existing:
        topic = existing
    else:
        topic = Topic(key=proposal.proposed_key, label_sr=body.label_sr, is_active=True)
        db.add(topic)
        await db.flush()

    proposal.status = "accepted"
    proposal.accepted_topic_id = topic.id
    log_action(db, user=current_user, action_type="accept", entity_type="topic_proposal",
               entity_id=proposal_id, old_status="pending", new_status="accepted")
    await db.commit()
    return {"id": proposal_id, "accepted": True, "topic_key": topic.key, "topic_id": topic.id}


@router.post("/proposals/{proposal_id}/reject")
async def reject_topic_proposal(
    proposal_id: int,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role("researcher", "admin")),
):
    proposal = await db.get(TopicProposal, proposal_id)
    if not proposal:
        raise HTTPException(status_code=404, detail="Predlog nije pronađen")
    proposal.status = "rejected"
    log_action(db, user=current_user, action_type="reject", entity_type="topic_proposal",
               entity_id=proposal_id, old_status="pending", new_status="rejected")
    await db.commit()
    return {"id": proposal_id, "rejected": True}


class MergeTopicsRequest(BaseModel):
    source_topic: str
    target_topic: str


@router.post("/merge")
async def merge_topics(
    req: MergeTopicsRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role("researcher", "admin")),
):
    """Spoji source_topic u target_topic — prebaci sve article_analysis zapise i deaktiviraj izvornu temu."""
    affected = await db.execute(
        text("SELECT COUNT(*) FROM article_analysis WHERE primary_topic = :src"),
        {"src": req.source_topic},
    )
    count = affected.scalar()
    if count == 0:
        raise HTTPException(status_code=404, detail=f"Tema '{req.source_topic}' nema članaka ili ne postoji")

    await db.execute(
        text("UPDATE article_analysis SET primary_topic = :tgt WHERE primary_topic = :src"),
        {"src": req.source_topic, "tgt": req.target_topic},
    )
    await db.execute(
        text("UPDATE topics SET is_active = FALSE WHERE key = :src"),
        {"src": req.source_topic},
    )

    log_action(db, user=current_user, action_type="merge_topics", entity_type="topic",
               entity_id=0, old_status=req.source_topic, new_status=req.target_topic)
    await db.commit()

    return {
        "source_topic": req.source_topic,
        "target_topic": req.target_topic,
        "articles_moved": count,
        "reversible": True,
        "reverse_hint": f"POST /topics/merge sa source='{req.target_topic}' i target='{req.source_topic}' vraća unazad",
    }
