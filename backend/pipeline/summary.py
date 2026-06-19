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
        }
    finally:
        await pg.close()


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
