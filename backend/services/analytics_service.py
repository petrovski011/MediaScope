"""Deljeni analiticki sloj — agregacije nad clancima/analizom/izvorima.

Koriste ga i API endpointi i Celery taskovi (Faza 5+). Cuva owner-group
kontekst (United Media i dr.) na jednom mestu.
"""
from typing import Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import parse_date

METHODOLOGY_SILENCE_NOTE = (
    "Tišina se računa samo nad skrejpovanim i analiziranim člancima. "
    "Odsustvo pokrivenosti ne mora značiti namernu cenzuru."
)


async def owner_group_map(db: AsyncSession) -> dict:
    """Vraca {source_id: owner_group}."""
    rows = (await db.execute(text("SELECT source_id, owner_group FROM sources"))).all()
    return {r.source_id: r.owner_group for r in rows}


def same_owner_group(source_ids: list, og_map: dict) -> bool:
    """True ako svi izvori dele istu (ne-NULL) vlasnicku grupu."""
    groups = {og_map.get(s) for s in source_ids if og_map.get(s)}
    return len(groups) == 1 and len(source_ids) > 1


async def topic_coverage(
    db: AsyncSession, topic: str, date_from: Optional[str], date_to: Optional[str],
    silence_min_total: int = 5, silence_min_sources: int = 3,
) -> dict:
    """Coverage matrica po izvoru za temu + silence analiza.

    Izvor je 'tih' ako ima 0 clanaka na temi dok tema ima >= silence_min_total clanaka
    kroz >= silence_min_sources drugih izvora.
    """
    params = {"topic": topic}
    df = ""
    if date_from:
        df += " AND a.published_at >= :date_from"; params["date_from"] = parse_date(date_from)
    if date_to:
        df += " AND a.published_at <= :date_to"; params["date_to"] = parse_date(date_to)

    # po izvoru: broj clanaka na temi + prosek politickog skora + dominantni framing
    per_source = (await db.execute(text(f"""
        SELECT s.source_id, s.name, s.owner_group,
               COUNT(a.id) AS article_count,
               AVG(aa.political_score) AS avg_political,
               AVG(aa.sensationalism) AS avg_sensationalism
        FROM sources s
        LEFT JOIN article_analysis aa ON aa.primary_topic = :topic
        LEFT JOIN articles a ON a.id = aa.article_id AND a.source_id = s.source_id {df}
        WHERE s.is_active = TRUE
        GROUP BY s.source_id, s.name, s.owner_group
        ORDER BY article_count DESC, s.source_id
    """), params)).all()

    rows = [{
        "source_id": r.source_id, "name": r.name, "owner_group": r.owner_group,
        "article_count": r.article_count or 0,
        "avg_political": round(float(r.avg_political), 3) if r.avg_political is not None else None,
        "avg_sensationalism": round(float(r.avg_sensationalism), 3) if r.avg_sensationalism is not None else None,
    } for r in per_source]

    total = sum(r["article_count"] for r in rows)
    covering = [r for r in rows if r["article_count"] > 0]
    silent = []
    if total >= silence_min_total and len(covering) >= silence_min_sources:
        silent = [r for r in rows if r["article_count"] == 0]

    return {
        "topic": topic,
        "total_articles": total,
        "sources_covering": [r["source_id"] for r in covering],
        "sources_silent": [r["source_id"] for r in silent],
        "by_source": rows,
    }


async def topic_framing_split(
    db: AsyncSession, topic: str, date_from: Optional[str], date_to: Optional[str],
) -> dict:
    """Distribucija framing okvira za temu (ukupno + po izvoru)."""
    params = {"topic": topic}
    df = ""
    if date_from:
        df += " AND a.published_at >= :date_from"; params["date_from"] = parse_date(date_from)
    if date_to:
        df += " AND a.published_at <= :date_to"; params["date_to"] = parse_date(date_to)

    overall = (await db.execute(text(f"""
        SELECT ft.name AS framing, COUNT(*) AS cnt, AVG(af.confidence) AS avg_conf
        FROM article_framings af
        JOIN framing_types ft ON ft.id = af.framing_type_id
        JOIN articles a ON a.id = af.article_id
        JOIN article_analysis aa ON aa.article_id = a.id AND aa.primary_topic = :topic
        WHERE 1=1 {df}
        GROUP BY ft.name
        ORDER BY cnt DESC
    """), params)).all()

    by_source = (await db.execute(text(f"""
        SELECT a.source_id, ft.name AS framing, COUNT(*) AS cnt
        FROM article_framings af
        JOIN framing_types ft ON ft.id = af.framing_type_id
        JOIN articles a ON a.id = af.article_id
        JOIN article_analysis aa ON aa.article_id = a.id AND aa.primary_topic = :topic
        WHERE 1=1 {df}
        GROUP BY a.source_id, ft.name
        ORDER BY a.source_id, cnt DESC
    """), params)).all()

    src_map: dict = {}
    for r in by_source:
        src_map.setdefault(r.source_id, []).append({"framing": r.framing, "count": r.cnt})

    return {
        "topic": topic,
        "framing_split": [
            {"framing": r.framing, "count": r.cnt,
             "avg_confidence": round(float(r.avg_conf), 3) if r.avg_conf is not None else None}
            for r in overall
        ],
        "by_source": src_map,
    }
