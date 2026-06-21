"""
Koordinaciona analiza — identifikacija uskladjenog izvestavanja.

Tri nivoa:
1. Copy-paste — visoka trigram slicnost naslova + isti dan (>= COPYPASTE_THRESHOLD)
2. Framing koord — ista tema + isti dan + politicki skor u istom smeru + 3+ izvora
3. Similar articles — za dati clanak, pronadji slicne iz drugih izvora

Metodoloski disclaimer: koordinacija NE dokazuje nameru.
Interpretacija ostaje na istrazivacu.
"""

from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, text, and_, desc
from typing import Optional

from database import get_db
from models.articles import Article
from models.sources import Source
from models.analysis import ArticleAnalysis
from api.deps import get_current_user, parse_date
from config import settings

router = APIRouter(prefix="/coordination", tags=["coordination"])

METHODOLOGY_NOTE = (
    "Koordinacija ne dokazuje nameru. "
    "Slicnost moze biti rezultat deljenja istog izvora, prenosa agencijskih vesti, "
    "ili slucajnog poklapanja. Interpretacija ostaje na istrazivacu."
)


@router.get("/copy-paste")
async def find_copy_paste_groups(
    date_from: Optional[str] = Query(default=None),
    date_to: Optional[str] = Query(default=None),
    source_ids: Optional[str] = Query(default=None),
    threshold: float = Query(default=None),
    limit: int = Query(default=30, ge=1, le=100),
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Pronalazi parove clanaka sa visokom tekstualnom slicnoscu.
    Primarno cita precomputed coordination_copypaste (pgvector cosine na lokalnim
    embeddingima — Faza 3). Ako embeddingi jos nisu generisani, pada na pg_trgm
    nad naslovima (isti dan) kao fallback.
    """
    thr = threshold or settings.COPYPASTE_THRESHOLD
    src_ids = [s.strip() for s in source_ids.split(",") if s.strip()] if source_ids else None

    # --- primarno: precomputed coordination_copypaste (embeddingi) ---
    cc_sql = """
        SELECT a.id AS a_id, a.title AS a_title, a.source_id AS a_src, a.published_at AS a_pub,
               b.id AS b_id, b.title AS b_title, b.source_id AS b_src, b.published_at AS b_pub,
               cc.similarity_score AS sim, cc.same_owner_group AS same_owner
        FROM coordination_copypaste cc
        JOIN articles a ON a.id = cc.article_id_a
        JOIN articles b ON b.id = cc.article_id_b
        WHERE cc.similarity_score >= :threshold
    """
    params = {"threshold": thr, "limit": limit}
    if date_from:
        cc_sql += " AND a.published_at >= :date_from"; params["date_from"] = parse_date(date_from)
    if date_to:
        cc_sql += " AND a.published_at <= :date_to"; params["date_to"] = parse_date(date_to)
    if src_ids:
        cc_sql += " AND (a.source_id = ANY(:srcs) OR b.source_id = ANY(:srcs))"; params["srcs"] = src_ids
    cc_sql += " ORDER BY cc.similarity_score DESC LIMIT :limit"

    rows = (await db.execute(text(cc_sql), params)).all()
    source = "embeddings"

    if not rows:
        # --- fallback: pg_trgm nad naslovima, isti dan ---
        source = "trigram_fallback"
        date_filter = ""
        if date_from:
            date_filter += " AND a1.published_at >= :date_from"
        if date_to:
            date_filter += " AND a1.published_at <= :date_to"
        source_filter = ""
        if src_ids:
            source_filter = " AND (a1.source_id = ANY(:srcs) OR a2.source_id = ANY(:srcs))"
        fb_sql = text(f"""
            SELECT a1.id AS a_id, a1.title AS a_title, a1.source_id AS a_src, a1.published_at AS a_pub,
                   a2.id AS b_id, a2.title AS b_title, a2.source_id AS b_src, a2.published_at AS b_pub,
                   similarity(a1.title, a2.title) AS sim, NULL::boolean AS same_owner
            FROM articles a1
            JOIN articles a2 ON (
                a1.id < a2.id AND a1.source_id != a2.source_id
                AND DATE(a1.published_at) = DATE(a2.published_at)
                AND similarity(a1.title, a2.title) >= :threshold
                AND length(a1.title) > 20 AND length(a2.title) > 20
            )
            WHERE 1=1 {date_filter} {source_filter}
            ORDER BY sim DESC LIMIT :limit
        """)
        rows = (await db.execute(fb_sql, params)).all()

    # Union-Find: grupiše sve međusobno slične članke u jednu grupu
    parent: dict = {}
    def _find(x):
        if x not in parent: parent[x] = x
        if parent[x] != x: parent[x] = _find(parent[x])
        return parent[x]
    def _union(x, y):
        parent[_find(x)] = _find(y)

    article_meta: dict = {}
    edge_sim: dict = {}  # root -> max sim in group
    for r in rows:
        article_meta[r.a_id] = {"id": r.a_id, "title": r.a_title, "source_id": r.a_src,
                                 "published_at": r.a_pub.isoformat() if r.a_pub else None}
        article_meta[r.b_id] = {"id": r.b_id, "title": r.b_title, "source_id": r.b_src,
                                 "published_at": r.b_pub.isoformat() if r.b_pub else None}
        _union(r.a_id, r.b_id)

    # After all unions, collect by root
    groups_map: dict = {}
    for aid in article_meta:
        root = _find(aid)
        groups_map.setdefault(root, []).append(article_meta[aid])

    # Max similarity per group
    for r in rows:
        root = _find(r.a_id)
        sim = float(r.sim)
        if root not in edge_sim or sim > edge_sim[root]:
            edge_sim[root] = sim

    groups = sorted(
        [{"articles": v, "size": len(v), "max_similarity": round(edge_sim.get(root, 0), 3)}
         for root, v in groups_map.items()],
        key=lambda x: (-x["size"], -x["max_similarity"])
    )

    return {
        "groups": groups,
        "threshold_used": thr,
        "total": len(groups),
        "source": source,
        "methodology_note": METHODOLOGY_NOTE,
    }


@router.get("/framing")
async def find_framing_coordination(
    date_from: Optional[str] = Query(default=None),
    date_to: Optional[str] = Query(default=None),
    min_sources: int = Query(default=2, ge=2),
    limit: int = Query(default=50),
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Pronalazi (tema, tip framinga) kombinacije koje vise izvora koristi.
    Racuna se uzivo iz article_framings (af → articles → article_analysis → framing_types),
    ista logika kao detect_coordination task. Vraca STVARNE tipove framinga
    (threat_frame, victim_frame, conflict_frame, ...), ne politicki smer.
    """
    sql = """
        SELECT aa.primary_topic AS topic,
               ft.id AS framing_type_id,
               ft.name AS framing_name,
               COUNT(DISTINCT a.source_id) AS source_count,
               ARRAY_AGG(DISTINCT a.source_id) AS sources,
               AVG(af.confidence) AS avg_confidence,
               COUNT(*) AS article_count
        FROM article_framings af
        JOIN articles a ON a.id = af.article_id
        JOIN article_analysis aa ON aa.article_id = a.id
        JOIN framing_types ft ON ft.id = af.framing_type_id
        WHERE aa.primary_topic IS NOT NULL
    """
    params: dict = {"min_sources": min_sources, "limit": limit}
    if date_from:
        sql += " AND a.published_at >= :date_from"; params["date_from"] = parse_date(date_from)
    if date_to:
        sql += " AND a.published_at <= :date_to"; params["date_to"] = parse_date(date_to)
    sql += """
        GROUP BY aa.primary_topic, ft.id, ft.name
        HAVING COUNT(DISTINCT a.source_id) >= :min_sources
        ORDER BY source_count DESC, article_count DESC
        LIMIT :limit
    """

    rows = (await db.execute(text(sql), params)).all()

    groups = [
        {
            "topic": r.topic,
            "framing_type_id": r.framing_type_id,
            "framing_name": r.framing_name,
            "source_count": r.source_count,
            "sources": list(r.sources) if r.sources else [],
            "avg_confidence": round(float(r.avg_confidence), 3) if r.avg_confidence is not None else None,
            "article_count": r.article_count,
        }
        for r in rows
    ]

    return {
        "groups": groups,
        "min_sources": min_sources,
        "total": len(groups),
        "methodology_note": METHODOLOGY_NOTE,
    }


@router.get("/similar/{article_id}")
async def find_similar_articles(
    article_id: int,
    limit: int = Query(default=10, ge=1, le=30),
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Za dati clanak pronalazi slicne clanke iz DRUGIH izvora.
    Primarno: pgvector cosine (semanticka slicnost, lokalni embeddingi).
    Fallback: pg_trgm nad naslovom ako clanak nema embedding.
    """
    article = await db.get(Article, article_id)
    if not article:
        raise HTTPException(status_code=404, detail="NOT_FOUND")

    has_emb = await db.scalar(text(
        "SELECT 1 FROM article_embeddings WHERE article_id = :aid AND embedding IS NOT NULL"
    ), {"aid": article_id})

    sim_thr = settings.SIMILAR_ARTICLES_THRESHOLD
    if has_emb:
        sql = text("""
            SELECT a.id, a.title, a.source_id, a.published_at, a.url,
                   1 - (e.embedding <=> q.embedding) AS sim_score,
                   aa.primary_topic, aa.political_score
            FROM article_embeddings q
            JOIN article_embeddings e ON e.article_id != q.article_id
            JOIN articles a ON a.id = e.article_id
            LEFT JOIN article_analysis aa ON aa.article_id = a.id
            WHERE q.article_id = :article_id
              AND a.source_id != :source_id
              AND (1 - (e.embedding <=> q.embedding)) >= :sim_thr
            ORDER BY e.embedding <=> q.embedding
            LIMIT :limit
        """)
        rows = (await db.execute(sql, {
            "article_id": article_id, "source_id": article.source_id,
            "sim_thr": sim_thr, "limit": limit,
        })).all()
    else:
        sql = text("""
            SELECT a.id, a.title, a.source_id, a.published_at, a.url,
                   similarity(a.title, :title) AS sim_score,
                   aa.primary_topic, aa.political_score
            FROM articles a
            LEFT JOIN article_analysis aa ON a.id = aa.article_id
            WHERE a.source_id != :source_id
              AND similarity(a.title, :title) > 0.3
              AND length(a.title) > 15
              AND a.id != :article_id
            ORDER BY sim_score DESC
            LIMIT :limit
        """)
        rows = (await db.execute(sql, {
            "title": article.title, "source_id": article.source_id,
            "article_id": article_id, "limit": limit,
        })).all()

    return {
        "article": {
            "id": article.id,
            "title": article.title,
            "source_id": article.source_id,
        },
        "similar": [
            {
                "id": r.id,
                "title": r.title,
                "source_id": r.source_id,
                "published_at": r.published_at.isoformat() if r.published_at else None,
                "url": r.url,
                "similarity_score": round(float(r.sim_score), 3),
                "primary_topic": r.primary_topic,
                "political_score": round(float(r.political_score), 3) if r.political_score else None,
            }
            for r in rows
        ],
        "methodology_note": METHODOLOGY_NOTE,
    }


@router.get("/network")
async def coordination_network(
    date_from: Optional[str] = Query(default=None),
    date_to: Optional[str] = Query(default=None),
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Mreza koordinacije: cvorovi = izvori, ivice = jacina koordinacije (copy-paste +
    framing + narativna). Ivice nose same_owner_group flag (vlasnicki kontekst).
    """
    from itertools import combinations

    og_rows = (await db.execute(text("SELECT source_id, name, owner_group FROM sources WHERE is_active = TRUE"))).all()
    og_map = {r.source_id: r.owner_group for r in og_rows}
    node_meta = {r.source_id: {"name": r.name, "owner_group": r.owner_group} for r in og_rows}

    edges: dict = {}
    node_weight: dict = {}

    def add_edge(a, b, w, typ):
        if a == b or a not in og_map or b not in og_map:
            return
        key = tuple(sorted([a, b]))
        e = edges.setdefault(key, {"weight": 0.0, "types": set()})
        e["weight"] += w
        e["types"].add(typ)
        node_weight[a] = node_weight.get(a, 0) + w
        node_weight[b] = node_weight.get(b, 0) + w

    cp_where = ""
    params = {}
    if date_from:
        cp_where += " AND cc.detected_at >= :date_from"; params["date_from"] = parse_date(date_from)
    if date_to:
        cp_where += " AND cc.detected_at <= :date_to"; params["date_to"] = parse_date(date_to)
    cp = (await db.execute(text(f"""
        SELECT a.source_id AS sa, b.source_id AS sb, cc.similarity_score AS s
        FROM coordination_copypaste cc
        JOIN articles a ON a.id = cc.article_id_a
        JOIN articles b ON b.id = cc.article_id_b
        WHERE a.source_id <> b.source_id {cp_where}
    """), params)).all()
    for r in cp:
        add_edge(r.sa, r.sb, float(r.s), "copypaste")

    for tbl, typ in [("coordination_framing", "framing"), ("coordination_narrative", "narrative")]:
        gw = ""
        gp = {}
        if date_from:
            gw += " AND date >= :date_from"; gp["date_from"] = parse_date(date_from)
        if date_to:
            gw += " AND date <= :date_to"; gp["date_to"] = parse_date(date_to)
        grows = (await db.execute(text(f"SELECT source_ids, coordination_score FROM {tbl} WHERE 1=1 {gw}"), gp)).all()
        for r in grows:
            srcs = list(r.source_ids or [])
            for a, b in combinations(srcs, 2):
                add_edge(a, b, float(r.coordination_score or 0.5) * 0.5, typ)

    edge_list = [
        {
            "source": a, "target": b,
            "weight": round(e["weight"], 2),
            "types": sorted(e["types"]),
            "same_owner_group": (og_map.get(a) is not None and og_map.get(a) == og_map.get(b)),
        }
        for (a, b), e in edges.items()
    ]
    nodes = [
        {"id": sid, "name": node_meta[sid]["name"], "owner_group": node_meta[sid]["owner_group"],
         "weight": round(node_weight.get(sid, 0), 2)}
        for sid in node_meta if node_weight.get(sid, 0) > 0
    ]

    return {
        "nodes": nodes,
        "edges": sorted(edge_list, key=lambda x: -x["weight"]),
        "methodology_note": METHODOLOGY_NOTE,
    }


@router.get("/network/actors")
async def network_actors(
    date_from: Optional[str] = Query(default=None),
    date_to: Optional[str] = Query(default=None),
    limit: int = Query(default=20, ge=5, le=50),
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Matrica mediji × akteri — koliko puta svaki izvor pominje svakog aktera."""
    from api.deps import parse_date
    params: dict = {"limit": limit}
    df = ""
    if date_from:
        df += " AND a.published_at >= :date_from"; params["date_from"] = parse_date(date_from)
    if date_to:
        df += " AND a.published_at <= :date_to"; params["date_to"] = parse_date(date_to)

    rows = (await db.execute(text(f"""
        SELECT a.source_id, e.id AS entity_id, e.name AS entity_name,
               SUM(ae.mention_count) AS mentions
        FROM article_entities ae
        JOIN articles a ON a.id = ae.article_id
        JOIN entities e ON e.id = ae.entity_id
        WHERE e.is_political_actor = TRUE {df}
        GROUP BY a.source_id, e.id, e.name
        ORDER BY mentions DESC
        LIMIT :limit * 5
    """), params)).all()

    top_entities = list(dict.fromkeys(r.entity_name for r in rows))[:limit]
    top_sources = list(dict.fromkeys(r.source_id for r in rows))
    entity_id_map: dict = {r.entity_name: r.entity_id for r in rows}

    lookup: dict = {}
    for r in rows:
        if r.entity_name in top_entities:
            lookup[(r.source_id, r.entity_name)] = int(r.mentions)

    matrix_list = [
        {"source_id": src, "entity_name": ent, "entity_id": entity_id_map.get(ent), "count": lookup.get((src, ent), 0)}
        for src in top_sources for ent in top_entities
    ]

    return {
        "sources": top_sources,
        "entities": top_entities,
        "matrix": matrix_list,
        "methodology_note": METHODOLOGY_NOTE,
    }


@router.get("/network/topics")
async def network_topics(
    date_from: Optional[str] = Query(default=None),
    date_to: Optional[str] = Query(default=None),
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Matrica mediji × teme — dominacija tematskog prostora po izvoru."""
    from api.deps import parse_date
    params: dict = {}
    df = ""
    if date_from:
        df += " AND a.published_at >= :date_from"; params["date_from"] = parse_date(date_from)
    if date_to:
        df += " AND a.published_at <= :date_to"; params["date_to"] = parse_date(date_to)

    rows = (await db.execute(text(f"""
        SELECT a.source_id, aa.primary_topic AS topic,
               COUNT(*) AS article_count
        FROM article_analysis aa
        JOIN articles a ON a.id = aa.article_id
        WHERE aa.primary_topic IS NOT NULL {df}
        GROUP BY a.source_id, aa.primary_topic
        ORDER BY article_count DESC
    """), params)).all()

    top_topics = list(dict.fromkeys(r.topic for r in rows))[:20]
    top_sources = list(dict.fromkeys(r.source_id for r in rows))

    lookup: dict = {}
    for r in rows:
        if r.topic in top_topics:
            lookup[(r.source_id, r.topic)] = int(r.article_count)

    matrix_list = [
        {"source_id": src, "topic": t, "count": lookup.get((src, t), 0)}
        for src in top_sources for t in top_topics
    ]

    return {
        "sources": top_sources,
        "topics": top_topics,
        "matrix": matrix_list,
        "methodology_note": METHODOLOGY_NOTE,
    }


@router.get("/network/narratives")
async def network_narratives(
    date_from: Optional[str] = Query(default=None),
    date_to: Optional[str] = Query(default=None),
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Matrica mediji × narativi — koji izvor širi koje narative."""
    from api.deps import parse_date
    params: dict = {}
    df = ""
    if date_from:
        df += " AND a.published_at >= :date_from"; params["date_from"] = parse_date(date_from)
    if date_to:
        df += " AND a.published_at <= :date_to"; params["date_to"] = parse_date(date_to)

    rows = (await db.execute(text(f"""
        SELECT a.source_id, nc.representative_name AS narrative_name, nc.id AS cluster_id,
               COUNT(*) AS article_count
        FROM narrative_proposals np
        JOIN articles a ON a.id = np.article_id
        JOIN narrative_clusters nc ON nc.id = np.cluster_id
        WHERE nc.proposal_count >= 2 {df}
        GROUP BY a.source_id, nc.representative_name, nc.id
        ORDER BY article_count DESC
    """), params)).all()

    top_narratives = list(dict.fromkeys(r.narrative_name for r in rows))[:15]
    top_sources = list(dict.fromkeys(r.source_id for r in rows))
    cluster_id_map: dict = {r.narrative_name: r.cluster_id for r in rows}

    lookup: dict = {}
    for r in rows:
        if r.narrative_name in top_narratives:
            lookup[(r.source_id, r.narrative_name)] = int(r.article_count)

    matrix_list = [
        {"source_id": src, "narrative_name": nar, "cluster_id": cluster_id_map.get(nar), "count": lookup.get((src, nar), 0)}
        for src in top_sources for nar in top_narratives
    ]

    return {
        "sources": top_sources,
        "narratives": top_narratives,
        "matrix": matrix_list,
        "methodology_note": METHODOLOGY_NOTE,
    }
