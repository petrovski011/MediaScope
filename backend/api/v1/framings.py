"""Framing tipovi (tematski specificni) + validacija AI predloga.

Metodologija v2: framing je tematski specifican. Globalni okviri (topic_id NULL)
vaze za sve teme; tematski su vezani za temu. AI predlaze, istrazivac validira.
"""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select, func, desc, text
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional

from api.deps import get_current_user, require_role, get_db
from api.v1.researcher_log import log_action
from models.analysis import Topic, FramingType, FramingTypeProposal, ArticleFraming

router = APIRouter(prefix="/framing", tags=["framing"])


class FramingTypeCreate(BaseModel):
    name: str
    topic_key: Optional[str] = None  # None = globalni
    description: Optional[str] = None


async def _topic_id(db: AsyncSession, topic_key: Optional[str]) -> Optional[int]:
    if not topic_key:
        return None
    return await db.scalar(select(Topic.id).where(Topic.key == topic_key))


@router.get("/topics")
async def list_topics(
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    rows = (await db.execute(select(Topic).where(Topic.is_active == True).order_by(Topic.key))).scalars().all()
    return {"topics": [{"id": t.id, "key": t.key, "label_sr": t.label_sr} for t in rows]}


@router.get("/types")
async def list_framing_types(
    topic: Optional[str] = Query(default=None, description="topic key; 'global' za samo globalne"),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    q = (
        select(
            FramingType,
            Topic.key.label("topic_key"),
            func.count(ArticleFraming.id).label("usage_count"),
        )
        .outerjoin(Topic, Topic.id == FramingType.topic_id)
        .outerjoin(ArticleFraming, ArticleFraming.framing_type_id == FramingType.id)
        .group_by(FramingType.id, Topic.key)
        .order_by(Topic.key.nullsfirst(), FramingType.name)
    )
    if topic == "global":
        q = q.where(FramingType.topic_id.is_(None))
    elif topic:
        tid = await _topic_id(db, topic)
        q = q.where((FramingType.topic_id == tid) | (FramingType.topic_id.is_(None)))

    rows = await db.execute(q)
    return {
        "framing_types": [
            {
                "id": ft.id,
                "name": ft.name,
                "topic_key": tkey,
                "description": ft.description,
                "is_validated": ft.is_validated,
                "usage_count": usage,
            }
            for ft, tkey, usage in rows.all()
        ]
    }


@router.get("/evolution")
async def framing_evolution(
    topic: str = Query(...),
    days: int = Query(default=30, ge=7, le=180),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Evolucija framing okvira kroz vreme za temu (dnevni udeo). Za stacked area chart."""
    rows = (await db.execute(text(f"""
        SELECT DATE(a.published_at) AS day, ft.name AS framing, COUNT(*) AS cnt
        FROM article_framings af
        JOIN framing_types ft ON ft.id = af.framing_type_id
        JOIN articles a ON a.id = af.article_id
        JOIN article_analysis aa ON aa.article_id = a.id AND aa.primary_topic = :topic
        WHERE a.published_at >= NOW() - INTERVAL '{days} days'
        GROUP BY DATE(a.published_at), ft.name
        ORDER BY day
    """), {"topic": topic})).all()

    framings = sorted({r.framing for r in rows})
    by_day: dict = {}
    for r in rows:
        d = r.day.isoformat()
        by_day.setdefault(d, {"date": d})[r.framing] = r.cnt
    return {
        "topic": topic,
        "framings": framings,
        "series": [by_day[d] for d in sorted(by_day)],
    }


@router.post("/types", status_code=201)
async def create_framing_type(
    body: FramingTypeCreate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role("researcher", "admin")),
):
    tid = await _topic_id(db, body.topic_key)
    if body.topic_key and tid is None:
        raise HTTPException(status_code=400, detail="Nepoznata tema")
    ft = FramingType(
        name=body.name.strip(),
        topic_id=tid,
        description=body.description,
        created_by=current_user.id,
        is_validated=True,
    )
    db.add(ft)
    await db.commit()
    await db.refresh(ft)
    return {"id": ft.id, "name": ft.name, "topic_key": body.topic_key, "is_validated": True}


@router.post("/types/{type_id}/validate")
async def validate_framing_type(
    type_id: int,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role("researcher", "admin")),
):
    ft = await db.get(FramingType, type_id)
    if not ft:
        raise HTTPException(status_code=404, detail="Framing tip nije pronađen")
    ft.is_validated = True
    await db.commit()
    return {"id": ft.id, "is_validated": True}


@router.delete("/types/{type_id}")
async def delete_framing_type(
    type_id: int,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role("admin")),
):
    ft = await db.get(FramingType, type_id)
    if not ft:
        raise HTTPException(status_code=404, detail="Framing tip nije pronađen")
    await db.delete(ft)
    await db.commit()
    return {"deleted": True}


@router.get("/proposals")
async def list_proposals(
    status: str = Query(default="pending"),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role("researcher", "admin")),
):
    rows = await db.execute(
        select(FramingTypeProposal, Topic.key.label("topic_key"))
        .outerjoin(Topic, Topic.id == FramingTypeProposal.topic_id)
        .where(FramingTypeProposal.status == status, FramingTypeProposal.occurrences >= 3)
        .order_by(desc(FramingTypeProposal.occurrences), desc(FramingTypeProposal.created_at))
    )
    return {
        "proposals": [
            {
                "id": p.id,
                "name": p.name,
                "topic_key": tkey,
                "description": p.description,
                "supporting_text": p.supporting_text,
                "occurrences": p.occurrences,
                "article_id": p.article_id,
                "article_ids": p.article_ids or [],
                "created_at": p.created_at.isoformat() if p.created_at else None,
            }
            for p, tkey in rows.all()
        ]
    }


@router.post("/proposals/{proposal_id}/approve")
async def approve_proposal(
    proposal_id: int,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role("researcher", "admin")),
):
    p = await db.get(FramingTypeProposal, proposal_id)
    if not p:
        raise HTTPException(status_code=404, detail="Predlog nije pronađen")
    if p.status != "pending":
        raise HTTPException(status_code=409, detail="Predlog je već obrađen")

    # Promovisi u framing_types (validiran), osim ako vec postoji
    dup_q = select(FramingType.id).where(FramingType.name == p.name)
    dup_q = dup_q.where(FramingType.topic_id.is_(None) if p.topic_id is None
                        else FramingType.topic_id == p.topic_id)
    existing = await db.scalar(dup_q)
    if not existing:
        db.add(FramingType(
            name=p.name, topic_id=p.topic_id, description=p.description,
            created_by=current_user.id, is_validated=True,
        ))
    p.status = "approved"
    p.reviewed_by = current_user.id
    p.reviewed_at = datetime.now(timezone.utc)
    log_action(db, user=current_user, action_type="approve", entity_type="framing_proposal",
               entity_id=proposal_id, old_status="pending", new_status="approved")
    await db.commit()
    return {"id": p.id, "status": "approved"}


@router.post("/proposals/{proposal_id}/reject")
async def reject_proposal(
    proposal_id: int,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role("researcher", "admin")),
):
    p = await db.get(FramingTypeProposal, proposal_id)
    if not p:
        raise HTTPException(status_code=404, detail="Predlog nije pronađen")
    p.status = "rejected"
    p.reviewed_by = current_user.id
    p.reviewed_at = datetime.now(timezone.utc)
    log_action(db, user=current_user, action_type="reject", entity_type="framing_proposal",
               entity_id=proposal_id, old_status="pending", new_status="rejected")
    await db.commit()
    return {"id": p.id, "status": "rejected"}
