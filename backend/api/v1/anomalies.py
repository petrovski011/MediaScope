"""Anomalije (statisticka detekcija) + period typing za kontekstualizaciju."""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional

from api.deps import get_current_user, require_role, get_db, parse_date
from models.coordination import Anomaly, PeriodType

router = APIRouter(prefix="/anomalies", tags=["anomalies"])


@router.get("")
async def list_anomalies(
    anomaly_type: Optional[str] = Query(default=None),
    date_from: Optional[str] = Query(default=None),
    date_to: Optional[str] = Query(default=None),
    source_ids: Optional[str] = Query(default=None),
    sort_by: Optional[str] = Query(default="date"),
    sort_dir: Optional[str] = Query(default="desc"),
    limit: int = Query(default=25, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    from sqlalchemy import func, asc

    _SORTABLE = {"date": Anomaly.date, "deviation_pct": Anomaly.deviation_pct, "anomaly_type": Anomaly.anomaly_type}
    sort_col = _SORTABLE.get(sort_by, Anomaly.date)
    order_fn = asc if sort_dir == "asc" else desc

    base = select(Anomaly)
    if anomaly_type:
        base = base.where(Anomaly.anomaly_type == anomaly_type)
    if date_from:
        base = base.where(Anomaly.date >= parse_date(date_from))
    if date_to:
        base = base.where(Anomaly.date <= parse_date(date_to))
    if source_ids:
        src_list = [s.strip() for s in source_ids.split(",") if s.strip()]
        if src_list:
            base = base.where(Anomaly.source_id.in_(src_list))

    total = (await db.execute(select(func.count()).select_from(base.subquery()))).scalar_one()

    secondary = desc(Anomaly.deviation_pct) if sort_by != "deviation_pct" else desc(Anomaly.date)
    rows = (await db.execute(
        base.order_by(order_fn(sort_col), secondary).limit(limit).offset(offset)
    )).scalars().all()

    return {
        "total": total,
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
