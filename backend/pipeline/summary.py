"""
Morning summary — AI-generisani dnevni pregled medijskog pejzaza.

Generise se svako jutro u 07:00 i cuva u Redis (TTL 36h).
Format: strukturirani JSON sa narativnim textom + kljucnim podacima.
"""

import json
import logging
from datetime import date, timedelta

import anthropic
import asyncpg

from config import settings

logger = logging.getLogger(__name__)

REDIS_KEY = "mediascope:summary:{date}"
REDIS_TTL = 36 * 3600  # 36 sati

PG_DSN = settings.DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")

SUMMARY_SYSTEM = """Ti si analiticar medijskog sadrzaja za SHARE Fondaciju.
Pises dnevne preglede medijskog pejzaza Srbije — kratke, faktografske, bez dramatizacije.
Fokus: objektivna analiza podataka, identifikacija obrazaca, ne politicki stavovi.
Pisi na srpskom jeziku (latinica). Budi koncizan — maksimum 300 reci po sekciji."""


async def _fetch_daily_stats(target_date: date) -> dict:
    """Dohvata statistike za dati dan iz PostgreSQL."""
    pg = await asyncpg.connect(PG_DSN)
    try:
        next_date = target_date + timedelta(days=1)

        total = await pg.fetchval(
            "SELECT COUNT(*) FROM articles WHERE published_at >= $1 AND published_at < $2",
            target_date, next_date,
        )
        analyzed = await pg.fetchval(
            """SELECT COUNT(*) FROM article_analysis aa
               JOIN articles a ON aa.article_id = a.id
               WHERE a.published_at >= $1 AND a.published_at < $2""",
            target_date, next_date,
        )
        topics = await pg.fetch(
            """SELECT aa.primary_topic, COUNT(*) as cnt
               FROM article_analysis aa
               JOIN articles a ON aa.article_id = a.id
               WHERE a.published_at >= $1 AND a.published_at < $2
               AND aa.primary_topic IS NOT NULL
               GROUP BY aa.primary_topic ORDER BY cnt DESC LIMIT 5""",
            target_date, next_date,
        )
        political = await pg.fetch(
            """SELECT a.source_id, AVG(aa.political_score) as avg_score, COUNT(*) as cnt
               FROM article_analysis aa
               JOIN articles a ON aa.article_id = a.id
               WHERE a.published_at >= $1 AND a.published_at < $2
               AND aa.political_score IS NOT NULL
               GROUP BY a.source_id ORDER BY avg_score DESC""",
            target_date, next_date,
        )
        top_entities = await pg.fetch(
            """SELECT e.name, e.entity_type, SUM(ae.mention_count) as total
               FROM article_entities ae
               JOIN entities e ON ae.entity_id = e.id
               JOIN articles a ON ae.article_id = a.id
               WHERE a.published_at >= $1 AND a.published_at < $2
               GROUP BY e.name, e.entity_type ORDER BY total DESC LIMIT 10""",
            target_date, next_date,
        )
        copypaste = await pg.fetchval(
            """SELECT COUNT(*) FROM (
               SELECT a1.id FROM articles a1
               JOIN articles a2 ON (
                   a1.id < a2.id AND a1.source_id != a2.source_id
                   AND DATE(a1.published_at) = $1
                   AND DATE(a2.published_at) = $1
                   AND similarity(a1.title, a2.title) >= 0.85
               )
               WHERE a1.published_at >= $1 AND a1.published_at < $2
            ) t""",
            target_date, next_date,
        )

        # D2: raspodela narativa po delovima dana (samo exact-time izvori)
        daypart_rows = await pg.fetch(
            """
            SELECT
                CASE
                    WHEN EXTRACT(HOUR FROM a.published_at) BETWEEN 6 AND 11 THEN 'jutro'
                    WHEN EXTRACT(HOUR FROM a.published_at) BETWEEN 12 AND 17 THEN 'podne'
                    WHEN EXTRACT(HOUR FROM a.published_at) BETWEEN 18 AND 23 THEN 'vece'
                    ELSE 'noc'
                END AS daypart,
                n.name AS narrative_name,
                COUNT(*) AS cnt
            FROM article_narratives an
            JOIN articles a ON a.id = an.article_id
            JOIN narratives n ON n.id = an.narrative_id
            JOIN sources s ON s.source_id = a.source_id
            WHERE a.published_at >= $1 AND a.published_at < $2
              AND n.is_validated = TRUE
              AND COALESCE(s.has_timestamp_time, TRUE) = TRUE
            GROUP BY daypart, n.name
            ORDER BY daypart, cnt DESC
            """,
            target_date, next_date,
        )
        daypart_by_slot: dict = {}
        for r in daypart_rows:
            daypart_by_slot.setdefault(r["daypart"], []).append(r["narrative_name"])

        return {
            "date": target_date.isoformat(),
            "total_articles": int(total or 0),
            "analyzed_articles": int(analyzed or 0),
            "top_topics": [{"topic": r["primary_topic"], "count": int(r["cnt"])} for r in topics],
            "political_by_source": [
                {"source_id": r["source_id"], "avg_score": round(float(r["avg_score"]), 3)}
                for r in political
            ],
            "top_entities": [
                {"name": r["name"], "type": r["entity_type"], "mentions": int(r["total"])}
                for r in top_entities
            ],
            "copypaste_pairs": int(copypaste or 0),
            "narratives_by_daypart": {k: v[:3] for k, v in daypart_by_slot.items()},
        }
    finally:
        await pg.close()


async def persist_summary(summary: dict) -> None:
    """Upisuje dnevni pregled u daily_summaries tabelu (istorijat, preživljava Redis TTL).

    Pun narrative+stats se cuva kao JSON u summary_text; strukturne kolone radi upita.
    """
    stats = summary.get("stats", {})
    narrative = summary.get("narrative", {})
    summary_date = date.fromisoformat(summary["date"]) if isinstance(summary["date"], str) else summary["date"]
    pg = await asyncpg.connect(PG_DSN)
    try:
        await pg.execute(
            """
            INSERT INTO daily_summaries
                (date, summary_text, top_topics, article_count, coordination_alerts, model_used, generated_at)
            VALUES ($1, $2, $3, $4, $5, $6, NOW())
            ON CONFLICT (date) DO UPDATE SET
                summary_text = EXCLUDED.summary_text,
                top_topics = EXCLUDED.top_topics,
                article_count = EXCLUDED.article_count,
                coordination_alerts = EXCLUDED.coordination_alerts,
                model_used = EXCLUDED.model_used,
                generated_at = EXCLUDED.generated_at
            """,
            summary_date,
            json.dumps(summary, ensure_ascii=False),
            [t["topic"] for t in stats.get("top_topics", []) if t.get("topic")],
            int(stats.get("total_articles", 0)),
            int(stats.get("copypaste_pairs", 0)),
            summary.get("model_used"),
        )
    finally:
        await pg.close()


def _daypart_text(stats: dict) -> str:
    dp = stats.get("narratives_by_daypart", {})
    if not dp:
        return ""
    ORDER = [("jutro", "Jutro 06-12"), ("podne", "Podne 12-18"), ("vece", "Veče 18-24"), ("noc", "Noć 00-06")]
    lines = ["\nNarativi po delovima dana (samo src sa tacnim vremenom):"]
    for key, label in ORDER:
        narrs = dp.get(key)
        if narrs:
            lines.append(f"  {label}: {', '.join(narrs)}")
    return "\n".join(lines) + "\n" if len(lines) > 1 else ""


def generate_summary(stats: dict) -> dict:
    """Poziva Claude da generise narativni pregled na osnovu statistika."""
    client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)

    prompt = f"""Na osnovu sledecih podataka o srpskim medijima za {stats['date']}, napravi dnevni pregled.

PODACI:
- Ukupno objavljenih clanaka: {stats['total_articles']}
- Analizirano AI-jem: {stats['analyzed_articles']}
- Copy-paste parova (>85% slicnost): {stats['copypaste_pairs']}

Top teme:
{chr(10).join(f"  {i+1}. {t['topic']}: {t['count']} clanaka" for i, t in enumerate(stats['top_topics']))}

Prosecni politicki skor po izvoru (>0 = pro-vladino, <0 = opoziciono):
{chr(10).join(f"  {p['source_id']}: {'+' if p['avg_score'] > 0 else ''}{p['avg_score']:.2f}" for p in stats['political_by_source'][:8])}

Najcesci akteri:
{chr(10).join(f"  {e['name']} ({e['type']}): {e['mentions']} pominjanja" for e in stats['top_entities'][:8])}
{_daypart_text(stats)}
Napravi strukturirani pregled u JSON formatu:
{{
  "headline": "Kratki naslov dana (max 10 reci)",
  "overview": "Kratki pregled dana (2-3 recenice, faktografski)",
  "key_themes": ["Tema 1 sa kratkim opisom", "Tema 2", "Tema 3"],
  "notable_actors": ["Akter 1 i kontekst", "Akter 2"],
  "coordination_note": "Napomena o copy-paste/koordinaciji ako relevantno, ili null",
  "editorial_note": "Strucna napomena istrazivaca za interpretaciju (ili null)"
}}

Vrati ISKLJUCIVO validan JSON."""

    msg = client.messages.create(
        model=settings.ANTHROPIC_MODEL,
        max_tokens=1000,
        system=SUMMARY_SYSTEM,
        messages=[{"role": "user", "content": prompt}],
    )

    raw = msg.content[0].text.strip()
    if raw.startswith("```"):
        lines = raw.split("\n")
        raw = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:]).strip()

    narrative = json.loads(raw)
    return {
        "date": stats["date"],
        "generated_at": None,  # caller sets this
        "stats": stats,
        "narrative": narrative,
        "model_used": settings.ANTHROPIC_MODEL,
    }
