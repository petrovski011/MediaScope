"""Istraživački log — praćenje i revert akcija istraživača."""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, func, update as sa_update
from typing import Optional

from api.deps import get_current_user, require_role, get_db
from models.userspace import ResearcherAction
from models.analysis import (
    Narrative, NarrativeCluster, NarrativeProposal,
    FramingTypeProposal, TopicProposal,
)

router = APIRouter(prefix="/researcher-log", tags=["researcher-log"])


def log_action(db, *, user, action_type, entity_type, entity_id, old_status=None, new_status=None):
    """Upisuje trag istraživačke odluke (caller radi commit)."""
    db.add(ResearcherAction(
        user_id=getattr(user, "id", None),
        action_type=action_type,
        entity_type=entity_type,
        entity_id=entity_id,
        old_status=old_status,
        new_status=new_status,
    ))


# entity_type-ovi koji su jednoklik-reverzibilni
_REVERTIBLE_ENTITY_TYPES = {"narrative_cluster", "framing_proposal", "topic_proposal"}


def _is_revertible(r: ResearcherAction) -> bool:
    if r.reverted_at is not None:
        return False
    if r.entity_type in _REVERTIBLE_ENTITY_TYPES:
        return True
    if r.entity_type == "narrative" and r.action_type in ("validate", "unvalidate"):
        return True
    return False


@router.get("")
async def list_actions(
    action_type: Optional[str] = Query(default=None),
    entity_type: Optional[str] = Query(default=None),
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role("researcher", "admin")),
):
    q = select(ResearcherAction)
    if action_type:
        q = q.where(ResearcherAction.action_type == action_type)
    if entity_type:
        q = q.where(ResearcherAction.entity_type == entity_type)

    total = await db.scalar(select(func.count()).select_from(q.subquery()))
    rows = (await db.execute(
        q.order_by(desc(ResearcherAction.created_at)).limit(per_page).offset((page - 1) * per_page)
    )).scalars().all()

    return {
        "items": [
            {
                "id": r.id,
                "user_id": r.user_id,
                "action_type": r.action_type,
                "entity_type": r.entity_type,
                "entity_id": r.entity_id,
                "old_status": r.old_status,
                "new_status": r.new_status,
                "notes": r.notes,
                "created_at": r.created_at.isoformat() if r.created_at else None,
                "reverted_at": r.reverted_at.isoformat() if r.reverted_at else None,
                "reverted": r.reverted_at is not None,
                "is_revertible": _is_revertible(r),
            }
            for r in rows
        ],
        "total": total,
        "page": page,
        "per_page": per_page,
        "pages": (total + per_page - 1) // per_page if total else 1,
    }


@router.post("/{action_id}/revert")
async def revert_action(
    action_id: int,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role("researcher", "admin")),
):
    action = await db.get(ResearcherAction, action_id)
    if not action:
        raise HTTPException(status_code=404, detail="Akcija nije pronađena")
    if action.reverted_at is not None:
        raise HTTPException(status_code=400, detail="Već vraćeno.")

    et = action.entity_type

    if et == "narrative_cluster":
        cluster = await db.get(NarrativeCluster, action.entity_id)
        if not cluster:
            raise HTTPException(status_code=404, detail="Klaster nije pronađen")
        cluster.status = "pending"
        cluster.accepted_narrative_id = None
        await db.execute(
            sa_update(NarrativeProposal)
            .where(NarrativeProposal.cluster_id == action.entity_id)
            .values(status="pending")
        )

    elif et == "framing_proposal":
        p = await db.get(FramingTypeProposal, action.entity_id)
        if not p:
            raise HTTPException(status_code=404, detail="Predlog nije pronađen")
        p.status = "pending"

    elif et == "topic_proposal":
        p = await db.get(TopicProposal, action.entity_id)
        if not p:
            raise HTTPException(status_code=404, detail="Predlog nije pronađen")
        p.status = "pending"

    elif et == "narrative" and action.action_type in ("validate", "unvalidate"):
        n = await db.get(Narrative, action.entity_id)
        if not n:
            raise HTTPException(status_code=404, detail="Narrativ nije pronađen")
        n.is_validated = (action.old_status == "true")
        if not n.is_validated:
            n.validated_at = None
            n.validated_by = None

    elif et == "entity":
        raise HTTPException(
            status_code=400,
            detail="Izmena entiteta se ispravlja ponovnim editovanjem, nije jednoklik-reverzibilna.",
        )

    else:
        raise HTTPException(status_code=400, detail="Ova akcija nije reverzibilna.")

    action.reverted_at = datetime.now(timezone.utc)
    await db.commit()
    return {"id": action_id, "reverted": True}
