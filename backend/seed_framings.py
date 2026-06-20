"""Seed skripta za topics + framing_types tabele. Idempotentna — pokretati po potrebi.

docker compose exec backend python seed_framings.py

Metodologija v2: framing tipovi su TEMATSKI SPECIFICNI. Globalni okviri (topic_id NULL)
vaze svuda; tematski okviri vezani su za konkretnu temu. AI predlaze nove, istrazivac validira.
"""
import asyncio
import asyncpg
from config import settings

# 16 tema iz prompt enuma (key, label_sr)
TOPICS = [
    ("POLITIKA", "Politika"),
    ("EU_INTEGRACIJE", "EU integracije"),
    ("KOSOVO", "Kosovo"),
    ("EKONOMIJA", "Ekonomija"),
    ("INFRASTRUKTURA", "Infrastruktura"),
    ("BEZBEDNOST", "Bezbednost"),
    ("MEDIJI_SLOBODA", "Mediji i sloboda"),
    ("PROTEST", "Protesti"),
    ("KULTURA", "Kultura"),
    ("SPORT", "Sport"),
    ("HRONIKA", "Hronika"),
    ("ZDRAVLJE", "Zdravlje"),
    ("OBRAZOVANJE", "Obrazovanje"),
    ("SPOLJNA_POLITIKA", "Spoljna politika"),
    ("LOKALNA_VLAST", "Lokalna vlast"),
    ("DRUSTVO", "Društvo"),
]

# Globalni okviri (topic_id = NULL) — vaze za sve teme
GLOBAL_FRAMES = [
    ("threat_frame",   "Okvir pretnje — tematizuje opasnost, krizu, napad na Srbiju ili institucije"),
    ("conflict_frame", "Okvir sukoba — suprotstavlja aktere (vlast vs opozicija, Srbija vs Zapad)"),
    ("victim_frame",   "Okvir žrtve — neko trpi posledice tuđih odluka ili nepravde"),
    ("progress_frame", "Okvir napretka — ističe uspehe, reforme, razvoj, pobede"),
    ("morality_frame", "Moralni okvir — etički sud, patriotizam, tradicija, dužnost"),
]

# Tematski specificni okviri: {topic_key: [(name, description), ...]}
TOPIC_FRAMES = {
    "PROTEST": [
        ("huliganstvo_frame",        "Protesti kao nasilje, huliganstvo i ugrožavanje javnog reda"),
        ("strani_projekat_frame",    "Protesti kao strani/inostrani projekat, 'obojena revolucija'"),
        ("demokratski_izraz_frame",  "Protesti kao legitiman demokratski izraz nezadovoljstva građana"),
        ("marginalizacija_frame",    "Protesti prikazani kao malobrojni, marginalni, beznačajni"),
    ],
    "KOSOVO": [
        ("suverenitet_frame",        "Kosovo kao pitanje suvereniteta i teritorijalnog integriteta"),
        ("izdaja_frame",             "Pregovori/ustupci kao izdaja nacionalnih interesa"),
        ("stabilnost_dijalog_frame", "Fokus na mir, stabilnost i evropski put kroz dijalog"),
        ("ugrozeni_srbi_frame",      "Srbi na Kosovu kao ugroženi i žrtve"),
    ],
    "EU_INTEGRACIJE": [
        ("uslovljavanje_frame",      "EU kao sila koja nameće uslove i pritiske Srbiji"),
        ("evropski_put_frame",       "EU integracije kao pozitivan razvojni i civilizacijski cilj"),
        ("licemerje_frame",          "EU kao licemerna, sa dvostrukim standardima prema Srbiji"),
        ("reforme_frame",            "Fokus na konkretne reforme i standarde koje treba ispuniti"),
    ],
}


async def main():
    dsn = settings.DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")
    pg = await asyncpg.connect(dsn)
    try:
        # 1. Topics
        topic_id_by_key = {}
        for key, label in TOPICS:
            tid = await pg.fetchval("SELECT id FROM topics WHERE key = $1", key)
            if not tid:
                tid = await pg.fetchval(
                    "INSERT INTO topics (key, label_sr, is_active) VALUES ($1, $2, TRUE) RETURNING id",
                    key, label,
                )
                print(f"  topic dodat: {key}")
            topic_id_by_key[key] = tid

        # 2. Globalni okviri (topic_id NULL)
        for name, desc in GLOBAL_FRAMES:
            exists = await pg.fetchval(
                "SELECT id FROM framing_types WHERE name = $1 AND topic_id IS NULL", name
            )
            if exists:
                continue
            await pg.execute(
                "INSERT INTO framing_types (name, topic_id, description, is_validated) "
                "VALUES ($1, NULL, $2, TRUE)",
                name, desc,
            )
            print(f"  globalni okvir dodat: {name}")

        # 3. Tematski okviri
        for topic_key, frames in TOPIC_FRAMES.items():
            tid = topic_id_by_key[topic_key]
            for name, desc in frames:
                exists = await pg.fetchval(
                    "SELECT id FROM framing_types WHERE name = $1 AND topic_id = $2", name, tid
                )
                if exists:
                    continue
                await pg.execute(
                    "INSERT INTO framing_types (name, topic_id, description, is_validated) "
                    "VALUES ($1, $2, $3, TRUE)",
                    name, tid, desc,
                )
                print(f"  [{topic_key}] okvir dodat: {name}")

        # Rezime
        total = await pg.fetchval("SELECT count(*) FROM framing_types")
        glob = await pg.fetchval("SELECT count(*) FROM framing_types WHERE topic_id IS NULL")
        print(f"\nframing_types ukupno: {total} (globalnih: {glob}, tematskih: {total - glob})")
        print(f"topics ukupno: {await pg.fetchval('SELECT count(*) FROM topics')}")
    finally:
        await pg.close()


asyncio.run(main())
