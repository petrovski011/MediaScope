"""Anomalije (statisticka detekcija) + period typing za kontekstualizaciju."""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional

from api.deps import get_current_user, require_role, get_db
from models.coordination import Anomaly, PeriodType

router = APIRouter(prefix="/anomalies", tags=["anomalies"])


@router.get("")
async def list_anomalies(
    anomaly_type: Optional[str] = Query(default=None),
    date_from: Optional[str] = Query(default=None),
    date_to: Optional[str] = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    q = select(Anomaly).order_by(desc(Anomaly.date), desc(Anomaly.deviation_pct))
    if anomaly_type:
        q = q.where(Anomaly.anomaly_type == anomaly_type)
    if date_from:
        q = q.where(Anomaly.date >= date_from)
    if date_to:
        q = q.where(Anomaly.date <= date_to)
    q = q.limit(limit)
    rows = (await db.execute(q)).scalars().all()
    return {
        "anomalies": [
            {
                "id": a.id,
                "anomaly_type": a.anomaly_type,
                "description": a.description,
                "topic": a.topic,
                "narrative_id": a.narrative_id,
                "source_id": a.source_id,
                "date": a.date,
                "baseline_value": a.baseline_value,
                "detected_value": a.detected_value,
                "deviation_pct": round(a.deviation_pct, 1) if a.deviation_pct is not None else None,
                "baseline_type": a.baseline_type,
            }
            for a in rows
        ]
    }


class PeriodTypeCreate(BaseModel):
    date_from: str
    date_to: str
    period_type: str  # electoral, crisis, calm
    note: Optional[str] = None


@router.get("/period-types")
async def list_period_types(
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    rows = (await db.execute(select(PeriodType).order_by(desc(PeriodType.date_from)))).scalars().all()
    return {
        "period_types": [
            {"id": p.id, "date_from": p.date_from, "date_to": p.date_to,
             "period_type": p.period_type, "note": p.note}
            for p in rows
        ]
    }


@router.post("/period-types", status_code=201)
async def create_period_type(
    body: PeriodTypeCreate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role("researcher", "admin")),
):
    p = PeriodType(
        date_from=body.date_from, date_to=body.date_to,
        period_type=body.period_type, note=body.note, created_by=current_user.id,
    )
    db.add(p)
    await db.commit()
    await db.refresh(p)
    return {"id": p.id, "period_type": p.period_type}


@router.delete("/period-types/{pt_id}")
async def delete_period_type(
    pt_id: int,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role("researcher", "admin")),
):
    p = await db.get(PeriodType, pt_id)
    if not p:
        raise HTTPException(status_code=404, detail="NOT_FOUND")
    await db.delete(p)
    await db.commit()
    return {"deleted": True}
