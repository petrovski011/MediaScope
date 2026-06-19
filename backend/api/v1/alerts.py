from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional

from api.deps import get_current_user, get_db
from models.coordination import Alert

router = APIRouter(prefix="/alerts", tags=["alerts"])


@router.get("")
async def list_alerts(
    unread_only: bool = Query(False),
    severity: Optional[str] = Query(None),
    limit: int = Query(50, le=200),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    q = select(Alert).order_by(desc(Alert.created_at)).limit(limit)
    if unread_only:
        q = q.where(Alert.is_read == False)
    if severity:
        q = q.where(Alert.severity == severity)

    rows = await db.execute(q)
    alerts = rows.scalars().all()

    unread_count = await db.scalar(
        select(func.count(Alert.id)).where(Alert.is_read == False)
    )

    return {
        "alerts": [
            {
                "id": a.id,
                "alert_type": a.alert_type,
                "severity": a.severity,
                "title": a.title,
                "description": a.description,
                "score": a.score,
                "source_ids": a.source_ids,
                "date": a.date,
                "is_read": a.is_read,
                "created_at": a.created_at.isoformat() if a.created_at else None,
            }
            for a in alerts
        ],
        "unread_count": unread_count,
        "total": len(alerts),
    }


@router.patch("/{alert_id}/read")
async def mark_alert_read(
    alert_id: int,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    alert = await db.get(Alert, alert_id)
    if not alert:
        raise HTTPException(status_code=404, detail="Alert nije pronađen")
    from datetime import datetime, timezone
    alert.is_read = True
    alert.read_by = current_user.id
    alert.read_at = datetime.now(timezone.utc)
    await db.commit()
    return {"ok": True}


@router.patch("/read-all")
async def mark_all_read(
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    from sqlalchemy import update
    from datetime import datetime, timezone
    await db.execute(
        update(Alert)
        .where(Alert.is_read == False)
        .values(is_read=True, read_by=current_user.id, read_at=datetime.now(timezone.utc))
    )
    await db.commit()
    return {"ok": True}
