"""Istrazivacki prostor: anotacije, sacuvane pretrage, watchliste."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, Any

from api.deps import get_current_user, get_db
from models.userspace import Watchlist, WatchlistItem, SavedSearch, Annotation

router = APIRouter(tags=["userspace"])


# ---- Anotacije ----
class AnnotationCreate(BaseModel):
    body: str


@router.get("/articles/{article_id}/annotations")
async def list_annotations(
    article_id: int,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    rows = (await db.execute(
        select(Annotation).where(Annotation.article_id == article_id).order_by(desc(Annotation.created_at))
    )).scalars().all()
    return {"annotations": [
        {"id": a.id, "body": a.body, "user_id": a.user_id,
         "created_at": a.created_at.isoformat() if a.created_at else None}
        for a in rows
    ]}


@router.post("/articles/{article_id}/annotations", status_code=201)
async def create_annotation(
    article_id: int,
    body: AnnotationCreate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    a = Annotation(article_id=article_id, user_id=current_user.id, body=body.body.strip())
    db.add(a)
    await db.commit()
    await db.refresh(a)
    return {"id": a.id, "body": a.body, "created_at": a.created_at.isoformat() if a.created_at else None}


@router.delete("/annotations/{annotation_id}")
async def delete_annotation(
    annotation_id: int,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    a = await db.get(Annotation, annotation_id)
    if not a:
        raise HTTPException(status_code=404, detail="NOT_FOUND")
    if a.user_id != current_user.id and current_user.role != "admin":
        raise HTTPException(status_code=403, detail="FORBIDDEN")
    await db.delete(a)
    await db.commit()
    return {"deleted": True}


# ---- Sacuvane pretrage ----
class SavedSearchCreate(BaseModel):
    name: Optional[str] = None
    query_params: Any


@router.get("/saved-searches")
async def list_saved_searches(
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    rows = (await db.execute(
        select(SavedSearch).where(SavedSearch.user_id == current_user.id).order_by(desc(SavedSearch.created_at))
    )).scalars().all()
    return {"saved_searches": [
        {"id": s.id, "name": s.name, "query_params": s.query_params,
         "created_at": s.created_at.isoformat() if s.created_at else None}
        for s in rows
    ]}


@router.post("/saved-searches", status_code=201)
async def create_saved_search(
    body: SavedSearchCreate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    s = SavedSearch(user_id=current_user.id, name=body.name, query_params=body.query_params)
    db.add(s)
    await db.commit()
    await db.refresh(s)
    return {"id": s.id, "name": s.name}


@router.delete("/saved-searches/{search_id}")
async def delete_saved_search(
    search_id: int,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    s = await db.get(SavedSearch, search_id)
    if not s or s.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="NOT_FOUND")
    await db.delete(s)
    await db.commit()
    return {"deleted": True}


# ---- Watchliste ----
class WatchlistCreate(BaseModel):
    name: str
    description: Optional[str] = None


@router.get("/watchlists")
async def list_watchlists(
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    rows = (await db.execute(
        select(Watchlist).where(Watchlist.user_id == current_user.id, Watchlist.is_active == True)
        .order_by(desc(Watchlist.created_at))
    )).scalars().all()
    return {"watchlists": [
        {"id": w.id, "name": w.name, "description": w.description}
        for w in rows
    ]}


@router.post("/watchlists", status_code=201)
async def create_watchlist(
    body: WatchlistCreate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    w = Watchlist(user_id=current_user.id, name=body.name, description=body.description, is_active=True)
    db.add(w)
    await db.commit()
    await db.refresh(w)
    return {"id": w.id, "name": w.name}


@router.delete("/watchlists/{watchlist_id}")
async def delete_watchlist(
    watchlist_id: int,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    w = await db.get(Watchlist, watchlist_id)
    if not w or w.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="NOT_FOUND")
    w.is_active = False
    await db.commit()
    return {"deleted": True}
