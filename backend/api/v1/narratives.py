from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional

from sqlalchemy import update as sa_update
from sqlalchemy.dialects.postgresql import insert as sa_insert

from api.deps import get_current_user, require_role, get_db
from api.v1.researcher_log import log_action
from models.analysis import Narrative, NarrativeProposal, ArticleNarrative, NarrativeDailyIntensity, NarrativeCluster

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
    log_action(db, user=current_user, action_type="validate", entity_type="narrative",
               entity_id=narrative_id, old_status="false", new_status="true")
    await db.commit()
    return {"id": n.id, "is_validated": True}


@router.patch("/{narrative_id}")
async def update_narrative(
    narrative_id: int,
    data: dict,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role("researcher", "admin")),
):
    """Ažuriranje narativa — npr. revert validacije: {is_validated: false}"""
    n = await db.get(Narrative, narrative_id)
    if not n:
        raise HTTPException(status_code=404, detail="Narrativ nije pronađen")
    if "is_validated" in data:
        new_validated = bool(data["is_validated"])
        n.is_validated = new_validated
        if not n.is_validated:
            n.validated_at = None
            n.validated_by = None
        if not new_validated:
            log_action(db, user=current_user, action_type="unvalidate", entity_type="narrative",
                       entity_id=narrative_id, old_status="true", new_status="false")
    else:
        # čista metadata izmena (bez promene validacije)
        log_action(db, user=current_user, action_type="edit", entity_type="narrative",
                   entity_id=narrative_id)
    if "name" in data:
        n.name = data["name"]
    if "description" in data:
        n.description = data["description"]
    await db.commit()
    return {"id": n.id, "is_validated": n.is_validated}


@router.get("/{narrative_id}/origin")
async def narrative_origin(
    narrative_id: int,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Poreklo i širenje narativa kroz medije.

    Podaci se pune noćno taskoom detect_narrative_origin.
    Ako task još nije pokrenuo, vraća prazno.
    """
    from sqlalchemy import text
    n = await db.get(Narrative, narrative_id)
    if not n:
        raise HTTPException(status_code=404, detail="Narativ nije pronađen")

    row = (await db.execute(
        text("SELECT * FROM narrative_origin_tracking WHERE narrative_id = :nid"),
        {"nid": narrative_id},
    )).first()

    if not row:
        # Compute on-the-fly from article_narratives if precomputed data missing
        live_rows = (await db.execute(
            text("""
                SELECT
                    a.source_id,
                    s.name AS source_name,
                    MIN(a.published_at) AS first_published_at,
                    COUNT(*) AS article_count
                FROM article_narratives an
                JOIN articles a ON a.id = an.article_id
                LEFT JOIN sources s ON s.source_id = a.source_id
                WHERE an.narrative_id = :nid AND a.published_at IS NOT NULL
                GROUP BY a.source_id, s.name
                ORDER BY first_published_at ASC
            """),
            {"nid": narrative_id},
        )).all()
        if not live_rows or len(live_rows) < 2:
            return {
                "narrative_id": narrative_id,
                "narrative_name": n.name,
                "origin": None,
                "spread_timeline": [],
                "origin_note": "Narativ nema dovoljno pokrivenosti kroz medije za prikaz origin trackinga (potrebno ≥2 izvora).",
            }
        first = live_rows[0]
        last = live_rows[-1]
        spread_hours = (last.first_published_at - first.first_published_at).total_seconds() / 3600
        has_exact = first.first_published_at.hour != 0 or first.first_published_at.minute != 0
        spread = [
            {
                "source_id": r.source_id,
                "source_name": r.source_name,
                "first_published_at": r.first_published_at.isoformat(),
                "exact_time": r.first_published_at.hour != 0 or r.first_published_at.minute != 0,
                "article_count": r.article_count,
                "hours_after_first": round((r.first_published_at - first.first_published_at).total_seconds() / 3600, 1),
            }
            for r in live_rows
        ]
        return {
            "narrative_id": narrative_id,
            "narrative_name": n.name,
            "origin": {
                "first_source_id": first.source_id,
                "first_published_at": first.first_published_at.isoformat(),
                "has_exact_time": has_exact,
                "total_sources": len(live_rows),
                "spread_hours": round(spread_hours, 1),
                "window_days": None,
                "computed_at": None,
            },
            "spread_timeline": spread,
            "origin_note": ("Računato uživo iz article_narratives — noćni task još nije pokrenuo preračunavanje."
                            + ("" if has_exact else " Prvi izvor nema tačno vreme objave (datum bez sata).")),
        }

    import json as _json
    spread = row.spread or []
    if isinstance(spread, str):
        spread = _json.loads(spread)

    has_exact = bool(row.has_exact_time)
    note = None
    if not has_exact:
        note = "Napomena: prvi zabeleženi izvor nema tačno vreme objave (datum bez sata) — vremenski redosled je indikativan."

    return {
        "narrative_id": narrative_id,
        "narrative_name": n.name,
        "origin": {
            "first_source_id": row.first_source_id,
            "first_published_at": row.first_published_at.isoformat() if row.first_published_at else None,
            "has_exact_time": has_exact,
            "total_sources": row.total_sources,
            "spread_hours": float(row.spread_hours) if row.spread_hours is not None else None,
            "window_days": row.window_days,
            "computed_at": row.computed_at.isoformat() if row.computed_at else None,
        },
        "spread_timeline": spread,
        "origin_note": note,
    }


@router.get("/{narrative_id}/citations")
async def narrative_citations(
    narrative_id: int,
    limit: int = Query(default=30, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    from models.articles import Article
    from models.sources import Source
    n = await db.get(Narrative, narrative_id)
    if not n:
        raise HTTPException(status_code=404, detail="Narativ nije pronađen")

    rows = (await db.execute(
        select(ArticleNarrative, Article, Source)
        .join(Article, Article.id == ArticleNarrative.article_id)
        .join(Source, Source.source_id == Article.source_id)
        .where(ArticleNarrative.narrative_id == narrative_id)
        .where(ArticleNarrative.supporting_text.isnot(None))
        .order_by(desc(Article.published_at))
        .limit(limit)
    )).all()

    return {
        "narrative_id": narrative_id,
        "narrative_name": n.name,
        "citations": [
            {
                "article_id": an.article_id,
                "source_id": a.source_id,
                "source_name": s.name,
                "title": a.title,
                "published_at": a.published_at,
                "url": a.url,
                "supporting_text": an.supporting_text,
                "confidence": an.confidence,
            }
            for an, a, s in rows
        ],
    }


@router.get("/proposals")
async def list_narrative_proposals(
    status: str = Query(default="pending"),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role("researcher", "admin")),
):
    rows = (await db.execute(
        select(NarrativeCluster)
        .where(NarrativeCluster.status == status, NarrativeCluster.proposal_count >= 2)
        .order_by(desc(NarrativeCluster.proposal_count), desc(NarrativeCluster.last_seen))
    )).scalars().all()
    return {
        "proposals": [
            {
                "id": c.id,
                "name": c.representative_name,
                "narrative_type": c.narrative_type,
                "occurrences": c.proposal_count,
                "description": None,
                "supporting_text": None,
                "created_at": c.first_seen.isoformat() if c.first_seen else None,
            }
            for c in rows
        ]
    }


@router.post("/proposals/{proposal_id}/approve")
async def approve_narrative_proposal(
    proposal_id: int,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role("researcher", "admin")),
):
    cluster = (await db.execute(
        select(NarrativeCluster).where(NarrativeCluster.id == proposal_id)
    )).scalar_one_or_none()
    if not cluster:
        raise HTTPException(404, "Klaster nije pronađen")
    if cluster.status != "pending":
        raise HTTPException(400, "Klaster nije u pending statusu")

    # Create narrative if not already exists
    existing = (await db.execute(
        select(Narrative).where(func.lower(Narrative.name) == cluster.representative_name.lower())
    )).scalar_one_or_none()

    if existing:
        narrative_id = existing.id
    else:
        new_narrative = Narrative(
            name=cluster.representative_name,
            narrative_type=cluster.narrative_type,
            description=f"Kreirano iz klastera: {cluster.representative_name}",
            is_validated=True,
            is_active=True,
        )
        db.add(new_narrative)
        await db.flush()
        narrative_id = new_narrative.id

    cluster.status = "accepted"
    cluster.accepted_narrative_id = narrative_id

    await db.execute(
        sa_update(NarrativeProposal)
        .where(NarrativeProposal.cluster_id == cluster.id)
        .values(status="approved")
    )

    # Backfill article_narratives from all proposals in this cluster
    proposals_for_backfill = (await db.execute(
        select(NarrativeProposal.article_id, NarrativeProposal.supporting_text)
        .where(NarrativeProposal.cluster_id == cluster.id)
        .where(NarrativeProposal.article_id.isnot(None))
    )).all()
    for p in proposals_for_backfill:
        await db.execute(
            sa_insert(ArticleNarrative).values(
                article_id=p.article_id,
                narrative_id=narrative_id,
                confidence=None,
                supporting_text=p.supporting_text,
            ).on_conflict_do_nothing(index_elements=["article_id", "narrative_id"])
        )

    log_action(db, user=current_user, action_type="approve", entity_type="narrative_cluster",
               entity_id=proposal_id, old_status="pending", new_status="accepted")
    await db.commit()
    return {"ok": True, "narrative_id": narrative_id, "backfilled": len(proposals_for_backfill)}


@router.post("/proposals/{proposal_id}/reject")
async def reject_narrative_proposal(
    proposal_id: int,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role("researcher", "admin")),
):
    cluster = (await db.execute(
        select(NarrativeCluster).where(NarrativeCluster.id == proposal_id)
    )).scalar_one_or_none()
    if not cluster:
        raise HTTPException(404, "Klaster nije pronađen")

    cluster.status = "rejected"
    await db.execute(
        sa_update(NarrativeProposal)
        .where(NarrativeProposal.cluster_id == cluster.id)
        .values(status="rejected")
    )
    log_action(db, user=current_user, action_type="reject", entity_type="narrative_cluster",
               entity_id=proposal_id, old_status="pending", new_status="rejected")
    await db.commit()
    return {"ok": True}


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
