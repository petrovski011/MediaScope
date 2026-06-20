from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional

from api.deps import get_current_user, require_role, get_db
from models.analysis import Narrative, NarrativeProposal, ArticleNarrative, NarrativeDailyIntensity

router = APIRouter(prefix="/narratives", tags=["narratives"])


class NarrativeCreate(BaseModel):
    name: str
    narrative_type: str = "thematic"
    description: Optional[str] = None


@router.get("")
async def list_narratives(
    validated: Optional[bool] = Query(default=None, description="filter po is_validated"),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    q = (
        select(
            Narrative,
            func.count(ArticleNarrative.id).label("article_count"),
        )
        .outerjoin(ArticleNarrative, ArticleNarrative.narrative_id == Narrative.id)
        .where(Narrative.is_active == True)
        .group_by(Narrative.id)
        .order_by(desc(func.count(ArticleNarrative.id)))
    )
    if validated is not None:
        q = q.where(Narrative.is_validated == validated)
    rows = await db.execute(q)
    result = []
    for narrative, count in rows.all():
        result.append({
            "id": narrative.id,
            "name": narrative.name,
            "narrative_type": narrative.narrative_type,
            "description": narrative.description,
            "is_validated": narrative.is_validated,
            "article_count": count,
            "created_at": narrative.created_at.isoformat() if narrative.created_at else None,
        })
    return {"narratives": result, "total": len(result)}


@router.post("")
async def create_narrative(
    body: NarrativeCreate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role("researcher", "admin")),
):
    narrative = Narrative(
        name=body.name,
        narrative_type=body.narrative_type,
        description=body.description,
        is_active=True,
        is_validated=False,
    )
    db.add(narrative)
    await db.commit()
    await db.refresh(narrative)
    return {
        "id": narrative.id,
        "name": narrative.name,
        "narrative_type": narrative.narrative_type,
        "description": narrative.description,
    }


@router.post("/{narrative_id}/validate")
async def validate_narrative(
    narrative_id: int,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role("researcher", "admin")),
):
    n = await db.get(Narrative, narrative_id)
    if not n:
        raise HTTPException(status_code=404, detail="Narrativ nije pronađen")
    n.is_validated = True
    n.validated_at = datetime.now(timezone.utc)
    n.validated_by = current_user.id
    await db.commit()
    return {"id": n.id, "is_validated": True}


@router.get("/proposals")
async def list_narrative_proposals(
    status: str = Query(default="pending"),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role("researcher", "admin")),
):
    rows = (await db.execute(
        select(NarrativeProposal)
        .where(NarrativeProposal.status == status)
        .order_by(desc(NarrativeProposal.occurrences), desc(NarrativeProposal.created_at))
    )).scalars().all()
    return {
        "proposals": [
            {
                "id": p.id,
                "name": p.name,
                "narrative_type": p.narrative_type,
                "description": p.description,
                "supporting_text": p.supporting_text,
                "occurrences": p.occurrences,
                "article_id": p.article_id,
                "created_at": p.created_at.isoformat() if p.created_at else None,
            }
            for p in rows
        ]
    }


@router.post("/proposals/{proposal_id}/approve")
async def approve_narrative_proposal(
    proposal_id: int,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role("researcher", "admin")),
):
    p = await db.get(NarrativeProposal, proposal_id)
    if not p:
        raise HTTPException(status_code=404, detail="Predlog nije pronađen")
    if p.status != "pending":
        raise HTTPException(status_code=409, detail="Predlog je već obrađen")

    existing = await db.scalar(select(Narrative.id).where(func.lower(Narrative.name) == p.name.lower()))
    if not existing:
        db.add(Narrative(
            name=p.name, narrative_type=p.narrative_type, description=p.description,
            is_active=True, is_validated=True,
            detected_at=p.created_at, validated_at=datetime.now(timezone.utc),
            validated_by=current_user.id,
        ))
    p.status = "approved"
    p.reviewed_by = current_user.id
    p.reviewed_at = datetime.now(timezone.utc)
    await db.commit()
    return {"id": p.id, "status": "approved"}


@router.post("/proposals/{proposal_id}/reject")
async def reject_narrative_proposal(
    proposal_id: int,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role("researcher", "admin")),
):
    p = await db.get(NarrativeProposal, proposal_id)
    if not p:
        raise HTTPException(status_code=404, detail="Predlog nije pronađen")
    p.status = "rejected"
    p.reviewed_by = current_user.id
    p.reviewed_at = datetime.now(timezone.utc)
    await db.commit()
    return {"id": p.id, "status": "rejected"}


@router.get("/{narrative_id}")
async def get_narrative(
    narrative_id: int,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    row = await db.get(Narrative, narrative_id)
    if not row:
        raise HTTPException(status_code=404, detail="Narrativ nije pronađen")

    article_count = await db.scalar(
        select(func.count(ArticleNarrative.id))
        .where(ArticleNarrative.narrative_id == narrative_id)
    )

    intensity_rows = await db.execute(
        select(NarrativeDailyIntensity)
        .where(NarrativeDailyIntensity.narrative_id == narrative_id)
        .order_by(NarrativeDailyIntensity.date)
    )
    intensity = [
        {
            "date": r.date,
            "source_id": r.source_id,
            "article_count": r.article_count,
            "avg_confidence": r.avg_confidence,
            "intensity_score": r.intensity_score,
        }
        for r in intensity_rows.scalars().all()
    ]

    return {
        "id": row.id,
        "name": row.name,
        "narrative_type": row.narrative_type,
        "description": row.description,
        "is_active": row.is_active,
        "is_validated": row.is_validated,
        "article_count": article_count,
        "daily_intensity": intensity,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


@router.delete("/{narrative_id}")
async def delete_narrative(
    narrative_id: int,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role("researcher", "admin")),
):
    row = await db.get(Narrative, narrative_id)
    if not row:
        raise HTTPException(status_code=404, detail="Narrativ nije pronađen")
    row.is_active = False
    await db.commit()
    return {"ok": True}
