"""Upravljanje entitetima/akterima: spajanje, razdvajanje, predlozi."""
import unicodedata

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List

from api.deps import get_current_user, require_role, get_db
from models.analysis import Entity

router = APIRouter(prefix="/entities", tags=["entities"])

# Srpska ćirilica → latinica za normalizaciju poređenja
_CYR_LAT = {
    'а':'a','б':'b','в':'v','г':'g','д':'d','ђ':'dj','е':'e','ж':'zh',
    'з':'z','и':'i','ј':'j','к':'k','л':'l','љ':'lj','м':'m','н':'n',
    'њ':'nj','о':'o','п':'p','р':'r','с':'s','т':'t','ћ':'c','у':'u',
    'ф':'f','х':'h','ц':'ts','ч':'ch','џ':'dz','ш':'sh',
}


def _normalize(name: str) -> str:
    s = name.lower()
    s = ''.join(_CYR_LAT.get(c, c) for c in s)
    s = unicodedata.normalize('NFD', s)
    s = ''.join(c for c in s if unicodedata.category(c) != 'Mn')
    return s.strip()


@router.get("/suggestions")
async def entity_merge_suggestions(
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role("researcher", "admin")),
):
    """Predlaže grupe aktera koji imaju isti normalizovani naziv (različita pisma/dijakritici)."""
    rows = (await db.execute(
        select(Entity.id, Entity.name, Entity.entity_type)
        .where(Entity.canonical_id == None)
        .order_by(Entity.name)
    )).all()

    groups: dict = {}
    for r in rows:
        key = (_normalize(r.name), r.entity_type or "")
        groups.setdefault(key, []).append({"id": r.id, "name": r.name, "entity_type": r.entity_type})

    suggestions = [
        {"normalized": k[0], "entity_type": k[1], "entities": v}
        for k, v in groups.items()
        if len(v) >= 2
    ]
    suggestions.sort(key=lambda x: -len(x["entities"]))
    return {"suggestions": suggestions[:200]}


@router.get("/groups")
async def list_entity_groups(
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Lista postojećih kanonskih grupacija sa aliasima."""
    rows = (await db.execute(text("""
        SELECT
            canon.id      AS canonical_id,
            canon.name    AS canonical_name,
            canon.entity_type,
            json_agg(json_build_object('id', e.id, 'name', e.name)) AS aliases
        FROM entities e
        JOIN entities canon ON canon.id = e.canonical_id
        GROUP BY canon.id, canon.name, canon.entity_type
        ORDER BY canon.name
    """))).all()

    return {
        "groups": [
            {
                "canonical_id": r.canonical_id,
                "canonical_name": r.canonical_name,
                "entity_type": r.entity_type,
                "aliases": r.aliases,
            }
            for r in rows
        ]
    }


class MergeRequest(BaseModel):
    canonical_id: int
    alias_ids: List[int]


@router.post("/merge")
async def merge_entities(
    body: MergeRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role("researcher", "admin")),
):
    """Spoji alias entitete u kanonski (postavi canonical_id)."""
    canonical = await db.get(Entity, body.canonical_id)
    if not canonical:
        raise HTTPException(404, "Canonical entitet nije pronađen")
    if canonical.canonical_id is not None:
        raise HTTPException(400, "Canonical entitet je sam alias drugog — prvo ga odvoji")

    merged = 0
    for alias_id in body.alias_ids:
        if alias_id == body.canonical_id:
            continue
        alias = await db.get(Entity, alias_id)
        if alias:
            alias.canonical_id = body.canonical_id
            merged += 1

    await db.commit()
    return {"merged": merged, "canonical_id": body.canonical_id, "canonical_name": canonical.name}


@router.delete("/{entity_id}/canonical")
async def decouple_entity(
    entity_id: int,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role("researcher", "admin")),
):
    """Odvoji entitet iz grupe (postavi canonical_id = NULL)."""
    entity = await db.get(Entity, entity_id)
    if not entity:
        raise HTTPException(404, "Entitet nije pronađen")
    entity.canonical_id = None
    await db.commit()
    return {"decoupled": True, "entity_id": entity_id, "name": entity.name}
