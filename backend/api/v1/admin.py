from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from typing import Optional

from database import get_db
from models.users import User
from models.articles import ScraperRun
from models.sources import Source
from models.analysis import CalibrationFeedback
from api.deps import require_role
from passlib.context import CryptContext

router = APIRouter(prefix="/admin", tags=["admin"])
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

_require_admin = Depends(require_role("admin"))


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


@router.get("/scraper/runs")
async def scraper_runs(
    source_id: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 50,
    current_user=_require_admin,
    db: AsyncSession = Depends(get_db),
):
    q = select(ScraperRun).order_by(desc(ScraperRun.started_at)).limit(limit)
    if source_id:
        q = q.where(ScraperRun.source_id == source_id)
    if status:
        q = q.where(ScraperRun.status == status)

    runs = (await db.execute(q)).scalars().all()
    return {
        "items": [
            {
                "id": r.id,
                "source_id": r.source_id,
                "started_at": r.started_at,
                "finished_at": r.finished_at,
                "status": r.status,
                "articles_found": r.articles_found,
                "articles_new": r.articles_new,
                "articles_updated": r.articles_updated,
                "duration_ms": r.duration_ms,
                "error_type": r.error_type,
            }
            for r in runs
        ]
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
