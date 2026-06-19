from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional

from api.deps import get_current_user, require_role, get_db
from models.analysis import Narrative, ArticleNarrative, NarrativeDailyIntensity

router = APIRouter(prefix="/narratives", tags=["narratives"])


class NarrativeCreate(BaseModel):
    name: str
    narrative_type: str = "thematic"
    description: Optional[str] = None


@router.get("")
async def list_narratives(
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    rows = await db.execute(
        select(
            Narrative,
            func.count(ArticleNarrative.id).label("article_count"),
        )
        .outerjoin(ArticleNarrative, ArticleNarrative.narrative_id == Narrative.id)
        .where(Narrative.is_active == True)
        .group_by(Narrative.id)
        .order_by(desc(func.count(ArticleNarrative.id)))
    )
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
