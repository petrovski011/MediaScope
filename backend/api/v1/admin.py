from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, EmailStr
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, func
from typing import Optional

import redis as redis_lib
from database import get_db
from models.users import User
from models.articles import ScraperRun, PipelineBatch
from models.sources import Source
from models.analysis import CalibrationFeedback
from api.deps import require_role
from config import settings
from passlib.context import CryptContext

router = APIRouter(prefix="/admin", tags=["admin"])
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

_require_admin = Depends(require_role("admin"))

REDIS_KEY_PAUSED = "mediascope:pipeline:paused"
REDIS_KEY_BATCH_ID = "mediascope:pipeline:current_batch_id"
REDIS_KEY_SCRAPER_PAUSED = "mediascope:scraper:paused"


def _redis():
    return redis_lib.from_url(settings.REDIS_URL, decode_responses=True)


class CreateUserRequest(BaseModel):
    email: EmailStr
    name: str
    password: str
    role: str = "viewer"


@router.get("/users")
async def list_users(current_user=_require_admin, db: AsyncSession = Depends(get_db)):
    users = (await db.execute(select(User).order_by(User.created_at))).scalars().all()
    return [
        {
            "id": u.id,
            "email": u.email,
            "name": u.name,
            "role": u.role,
            "is_active": u.is_active,
            "last_login": u.last_login,
        }
        for u in users
    ]


@router.post("/users", status_code=201)
async def create_user(
    req: CreateUserRequest,
    current_user=_require_admin,
    db: AsyncSession = Depends(get_db),
):
    existing = (await db.execute(select(User).where(User.email == req.email))).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=409, detail="Email already exists")

    user = User(
        email=req.email,
        name=req.name,
        hashed_password=pwd_context.hash(req.password),
        role=req.role,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return {"id": user.id, "email": user.email, "name": user.name, "role": user.role}


@router.put("/users/{user_id}")
async def update_user(
    user_id: int,
    data: dict,
    current_user=_require_admin,
    db: AsyncSession = Depends(get_db),
):
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="NOT_FOUND")

    if "role" in data:
        user.role = data["role"]
    if "is_active" in data:
        user.is_active = data["is_active"]
    if "password" in data and data["password"]:
        user.hashed_password = pwd_context.hash(data["password"])

    await db.commit()
    return {"id": user.id, "email": user.email, "role": user.role}


@router.delete("/users/{user_id}")
async def delete_user(
    user_id: int,
    current_user=_require_admin,
    db: AsyncSession = Depends(get_db),
):
    if user_id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot delete yourself")
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="NOT_FOUND")
    await db.delete(user)
    await db.commit()
    return {"deleted": True}


@router.get("/pipeline/status")
async def pipeline_status(current_user=_require_admin):
    r = _redis()
    paused = bool(r.get(REDIS_KEY_PAUSED))
    batch_id = r.get(REDIS_KEY_BATCH_ID)
    return {"paused": paused, "current_batch_id": batch_id}


@router.post("/pipeline/pause")
async def pipeline_pause(current_user=_require_admin):
    _redis().set(REDIS_KEY_PAUSED, "1")
    return {"paused": True}


@router.post("/pipeline/resume")
async def pipeline_resume(current_user=_require_admin):
    _redis().delete(REDIS_KEY_PAUSED)
    return {"paused": False}


@router.get("/scraper/status")
async def scraper_status(current_user=_require_admin):
    paused = bool(_redis().get(REDIS_KEY_SCRAPER_PAUSED))
    return {"paused": paused}


@router.post("/scraper/pause")
async def scraper_pause(current_user=_require_admin):
    _redis().set(REDIS_KEY_SCRAPER_PAUSED, "1")
    return {"paused": True}


@router.post("/scraper/resume")
async def scraper_resume(current_user=_require_admin):
    _redis().delete(REDIS_KEY_SCRAPER_PAUSED)
    return {"paused": False}


@router.get("/scraper/runs")
async def scraper_runs(
    source_id: Optional[str] = None,
    status: Optional[str] = None,
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    current_user=_require_admin,
    db: AsyncSession = Depends(get_db),
):
    base_q = select(ScraperRun)
    if source_id:
        base_q = base_q.where(ScraperRun.source_id == source_id)
    if status:
        base_q = base_q.where(ScraperRun.status == status)

    total = await db.scalar(select(func.count()).select_from(base_q.subquery()))

    runs_q = base_q.order_by(desc(ScraperRun.started_at)).limit(per_page).offset((page - 1) * per_page)
    runs = (await db.execute(runs_q)).scalars().all()

    return {
        "items": [
            {
                "id": r.id,
                "source_id": r.source_id,
                "started_at": r.started_at.isoformat() if r.started_at else None,
                "finished_at": r.finished_at.isoformat() if r.finished_at else None,
                "status": r.status,
                "articles_found": r.articles_found,
                "articles_new": r.articles_new,
                "articles_updated": r.articles_updated,
                "articles_skipped": r.articles_skipped,
                "duration_ms": r.duration_ms,
                "error_type": r.error_type,
                "error_message": r.error_message,
            }
            for r in runs
        ],
        "total": total,
        "page": page,
        "per_page": per_page,
        "pages": (total + per_page - 1) // per_page if total else 1,
    }


@router.get("/pipeline/batches")
async def pipeline_batches(
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    current_user=_require_admin,
    db: AsyncSession = Depends(get_db),
):
    base_q = select(PipelineBatch)
    total = await db.scalar(select(func.count()).select_from(base_q.subquery()))
    batches_q = base_q.order_by(desc(PipelineBatch.submitted_at)).limit(per_page).offset((page - 1) * per_page)
    batches = (await db.execute(batches_q)).scalars().all()
    return {
        "items": [
            {
                "id": b.id,
                "batch_id": b.batch_id,
                "batch_type": b.batch_type,
                "batch_date": b.batch_date,
                "status": b.status,
                "article_count": b.article_count,
                "articles_saved": b.articles_saved,
                "articles_failed": b.articles_failed,
                "submitted_at": b.submitted_at.isoformat() if b.submitted_at else None,
                "finished_at": b.finished_at.isoformat() if b.finished_at else None,
                "error_message": b.error_message,
            }
            for b in batches
        ],
        "total": total,
        "page": page,
        "per_page": per_page,
        "pages": (total + per_page - 1) // per_page if total else 1,
    }


@router.get("/calibration/feedback")
async def get_feedback(
    analysis_type: Optional[str] = None,
    is_correct: Optional[bool] = None,
    applied: Optional[bool] = None,
    current_user=_require_admin,
    db: AsyncSession = Depends(get_db),
):
    q = select(CalibrationFeedback).order_by(desc(CalibrationFeedback.created_at))
    if analysis_type:
        q = q.where(CalibrationFeedback.analysis_type == analysis_type)
    if is_correct is not None:
        q = q.where(CalibrationFeedback.is_correct == is_correct)
    if applied is not None:
        q = q.where(CalibrationFeedback.applied_to_pipeline == applied)

    rows = (await db.execute(q)).scalars().all()
    return {
        "items": [
            {
                "id": r.id,
                "user_id": r.user_id,
                "article_id": r.article_id,
                "analysis_type": r.analysis_type,
                "is_correct": r.is_correct,
                "comment": r.comment,
                "original_value": r.original_value,
                "corrected_value": r.corrected_value,
                "applied_to_pipeline": r.applied_to_pipeline,
                "created_at": r.created_at,
            }
            for r in rows
        ]
    }
