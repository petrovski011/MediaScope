"""AI seeding inicijalnog seta narativa iz istorijskog korpusa naslova.

Pokretati jednokratno (ili periodicno za osvezavanje):
    docker compose exec backend python seed_narratives.py

Narativi se upisuju sa is_validated=FALSE — istrazivac ih validira u UI-u
pre nego sto udju u katalog za AI mapiranje.
"""
import asyncio
import json

import anthropic
import asyncpg

from config import settings
from pipeline.prompts import NARRATIVE_SEED_SYSTEM, build_narrative_seed_prompt

PG_DSN = settings.DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")
SAMPLE_SIZE = 600  # naslova u uzorku (raspoređeno po izvorima/vremenu)


async def _fetch_headlines() -> list[str]:
    pg = await asyncpg.connect(PG_DSN)
    try:
        # Uzorak: najnoviji naslovi, raznovrsno po izvorima (max ~40 po izvoru)
        rows = await pg.fetch(
            """
            WITH ranked AS (
                SELECT a.title, a.source_id,
                       ROW_NUMBER() OVER (PARTITION BY a.source_id ORDER BY a.published_at DESC) AS rn
                FROM articles a
                WHERE a.title IS NOT NULL AND length(a.title) > 15
                  AND a.published_at >= NOW() - INTERVAL '120 days'
            )
            SELECT title, source_id FROM ranked WHERE rn <= 40
            ORDER BY source_id, rn
            LIMIT $1
            """,
            SAMPLE_SIZE,
        )
        return [f"[{r['source_id']}] {r['title']}" for r in rows]
    finally:
        await pg.close()


def _clean_json(raw: str) -> str:
    raw = raw.strip()
    if raw.startswith("```"):
        lines = raw.split("\n")
        raw = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:]).strip()
    return raw


async def _insert_narratives(narratives: list[dict]) -> int:
    pg = await asyncpg.connect(PG_DSN)
    inserted = 0
    try:
        for n in narratives:
            name = (n.get("name") or "").strip()
            if not name:
                continue
            ntype = (n.get("type") or "thematic").strip().lower()
            if ntype not in ("systemic", "thematic"):
                ntype = "thematic"
            desc = (n.get("description") or "").strip() or None
            examples = n.get("example_headlines") or []
            if examples and desc:
                desc = desc + "\n\nPrimeri: " + " | ".join(examples[:3])

            exists = await pg.fetchval("SELECT 1 FROM narratives WHERE LOWER(name)=LOWER($1)", name)
            if exists:
                print(f"  vec postoji: {name}")
                continue
            await pg.execute(
                """
                INSERT INTO narratives (name, narrative_type, description, is_active, is_validated, detected_at)
                VALUES ($1, $2, $3, TRUE, FALSE, NOW())
                """,
                name, ntype, desc,
            )
            inserted += 1
            print(f"  + [{ntype}] {name}")
        return inserted
    finally:
        await pg.close()


async def main():
    if not settings.ANTHROPIC_API_KEY:
        print("ANTHROPIC_API_KEY nije postavljen — prekidam.")
        return

    headlines = await _fetch_headlines()
    if len(headlines) < 30:
        print(f"Premalo naslova ({len(headlines)}) za seeding.")
        return
    print(f"Uzorak: {len(headlines)} naslova. Saljem AI-ju...")

    client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
    msg = client.messages.create(
        model=settings.ANTHROPIC_MODEL,
        max_tokens=4000,
        system=NARRATIVE_SEED_SYSTEM,
        messages=[{"role": "user", "content": build_narrative_seed_prompt(
            "\n".join(headlines),
            settings.NARRATIVE_SEED_COUNT_MIN if hasattr(settings, "NARRATIVE_SEED_COUNT_MIN") else 10,
            settings.NARRATIVE_SEED_COUNT_MAX if hasattr(settings, "NARRATIVE_SEED_COUNT_MAX") else 20,
        )}],
    )
    parsed = json.loads(_clean_json(msg.content[0].text))
    narratives = parsed.get("narratives", [])
    print(f"AI predlozio {len(narratives)} narativa. Upisujem (is_validated=FALSE)...")
    inserted = await _insert_narratives(narratives)
    print(f"\nUpisano novih: {inserted}. Validiraj ih u UI-u (stranica Narativi) pre mapiranja.")


if __name__ == "__main__":
    asyncio.run(main())
