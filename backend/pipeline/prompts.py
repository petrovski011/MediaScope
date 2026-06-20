"""
Promptovi za AI pipeline.
Obuhvata: NER + Tematska klasifikacija + Politicko pozicioniranje + Sentiment
+ TEMATSKI SPECIFICAN framing (katalog se injektuje iz baze).
Kombinovano u jedan poziv po clanku (one-pass hybrid).
"""
from typing import Optional

SYSTEM_PROMPT = """Ti si analiticar medijskog sadrzaja za SHARE Fondaciju, istrazivacku organizaciju
koja prati narative i propagandu u srpskim medijima.

Analiziras clanke sa sledecih srpskih portala:
- Pro-vladini/tabloidni: Informer, Kurir, Blic, Pink, SD, Srbija danas, Prva TV, Tanjug (drzavna agencija), RTS (javni servis)
- Nezavisni/opozicioni: N1, Nova, Danas, Radar, Vreme, Insajder, BIRN, Telegraf
- Neutralni/mixes: B92, Mondo, Politika

Politicki kontekst Srbije (Jun 2026):
- Vladajuca stranka: SNS (Aleksandar Vucic, predsednik)
- Kljucni opozicioni akteri: SSP, Srpska stranka Zavetnici, koalicija Srbija protiv nasilja
- Aktuelne teme: EU integracije, medijska sloboda, protesti, infrastrukturni projekti, Kosovo, ekonomija
- Tanjug je drzavna novinska agencija - njeni tekstovi se preuzimaju na pro-vladinim portalima

Tvoj zadatak je objektivna analiza - ne interpretiras politicke stavove,
vec identifikujes kako mediji izvestavaju i koje narative plasiraju.

Uvek vraci SAMO validan JSON. Nikada ne dodavaj objasnjenja van JSON strukture."""


def build_framing_catalog_text(framing_rows: list[dict]) -> str:
    """Gradi tekst kataloga framing okvira iz baze.

    framing_rows: lista dict-ova {name, description, topic_key} gde je topic_key None za globalne.
    Metodologija: globalni okviri vaze za sve teme; tematski SAMO za svoju temu.
    """
    global_frames = [r for r in framing_rows if not r.get("topic_key")]
    by_topic: dict[str, list[dict]] = {}
    for r in framing_rows:
        if r.get("topic_key"):
            by_topic.setdefault(r["topic_key"], []).append(r)

    lines = ["KATALOG FRAMING OKVIRA — koristi ISKLJUCIVO okvire navedene ovde.\n"]
    lines.append("GLOBALNI OKVIRI (primenljivi na svaku temu):")
    for r in global_frames:
        lines.append(f"- {r['name']}: {r['description']}")

    if by_topic:
        lines.append("\nTEMATSKI OKVIRI (koristi SAMO ako primarna tema clanka odgovara temi okvira):")
        for topic_key in sorted(by_topic):
            lines.append(f"[{topic_key}]")
            for r in by_topic[topic_key]:
                lines.append(f"- {r['name']}: {r['description']}")

    return "\n".join(lines)


def build_system(framing_catalog_text: Optional[str] = None, enable_caching: bool = True):
    """Vraca `system` vrednost za Anthropic poziv.

    Bez kataloga: obican string (SYSTEM_PROMPT).
    Sa katalogom: lista blokova [bazni prompt, katalog] sa cache_control na katalogu
    (identican kroz ceo batch -> kesira se jednom, cita 1500x).
    """
    if not framing_catalog_text:
        return SYSTEM_PROMPT

    catalog_block = {"type": "text", "text": framing_catalog_text}
    if enable_caching:
        catalog_block["cache_control"] = {"type": "ephemeral"}
    return [
        {"type": "text", "text": SYSTEM_PROMPT},
        catalog_block,
    ]


def build_mvp_prompt(article: dict) -> str:
    """
    Kombinovani MVP prompt: NER + Tema + Politicko pozicioniranje u jednom pozivu.
    """
    subtitle_line = f"Podnaslov: {article['subtitle']}\n" if article.get("subtitle") else ""
    text_excerpt = article["text"][:2000] if article.get("text") else ""

    return f"""Analiziraj sledeci novinarski clanak i vrati kompletan JSON sa svim analizama.

CLANAK:
Izvor: {article['source_id']}
Naslov: {article['title']}
{subtitle_line}Tekst: {text_excerpt}

Izvedi sledece analize:

## 1. NER (Entiteti)
Identifikuj SVE znacajne entitete (max 15):
- Osobe (politicari, novinari, javne licnosti, strucnjaci)
- Organizacije (stranke, institucije, kompanije, NGO)
- Mesta (samo relevantni za kontekst)

Normalizuj varijante istog entiteta (Vucic = Aleksandar Vucic = predsednik Srbije -> "Aleksandar Vucic").
Ne ukljucuj genericne pojmove ("vlada", "novinari") - samo konkretne aktere.

## 2. Tematska klasifikacija
Odredi primarnu temu (jednu) i sekundarne (max 3) sa confidence scorovima.
Koristi ove teme: POLITIKA, EU_INTEGRACIJE, KOSOVO, EKONOMIJA, INFRASTRUKTURA,
BEZBEDNOST, MEDIJI_SLOBODA, PROTEST, KULTURA, SPORT, HRONIKA,
ZDRAVLJE, OBRAZOVANJE, SPOLJNA_POLITIKA, LOKALNA_VLAST, DRUSTVO

Ako ne odgovara nijednoj, predlozi novu kao "NOVA_TEMA: NAZIV".

## 3. Politicko pozicioniranje
Proceni na tri ose:

1. POLITICKA OSA (-1.0 do +1.0):
   -1.0 = izrazito opoziciono, 0.0 = neutralno, +1.0 = izrazito pro-vladino
   Ovo je objektivna mera stava clanka prema vladajucoj strukturi (SNS/Vucic).

2. VREDNOSNA OSA (-1.0 do +1.0):
   -1.0 = izrazito progresivno, 0.0 = neutralno, +1.0 = izrazito konzervativno

3. SENZACIONALIZAM (0.0 do 1.0):
   0.0 = potpuno faktografski, 1.0 = izrazito senzacionalisticki

4. SENTIMENT clanka (MORA biti tacno jedna od ove 4 vrednosti):
   "positive" | "negative" | "neutral" | "mixed"
   Nikada ne koristi druge reci.

Uzmi u obzir: izbor reci, citiranje izvora, selekciju cinjenica, naslove i emotivni naboj.

Za svaki skor dodaj kratko obrazlozenje (1-2 recenice na srpskom latinici, konkretni signali iz teksta,
ne ponavljaj skor kao broj — objasni ZASTO).

## 4. Framing (narativni okvir) — TEMATSKI SPECIFICAN
Pogledaj KATALOG FRAMING OKVIRA u sistemskim instrukcijama. Za framing vazi:
- Uvek su dostupni GLOBALNI okviri.
- TEMATSKI okviri se koriste SAMO ako odgovaraju primarnoj temi koju si odredio (npr. tematski
  okviri za KOSOVO se NE koriste ako je clanak o PROTEST-u).
- Prepoznaj sve okvire koji su JASNO prisutni (ne pretpostavljaj). Za svaki: tacan naziv iz kataloga,
  confidence (0.0-1.0) i kratak citat iz clanka (supporting_text).
- Ako je okvir JASNO prisutan ali NIJE u katalogu, predlozi nov u "new_framing_proposals"
  (naziv u stilu "..._frame", opis, citat). Ne izmisljaj okvire bez osnova.
- Ako nijedan okvir nije izrazit, vrati praznu listu.

Vrati ISKLJUCIVO ovaj JSON (bez ikakvih objasnjenja van JSON-a):
{{
  "entities": [
    {{
      "name": "Ime Prezime",
      "type": "person",
      "mention_count": 3,
      "has_quote": true,
      "is_main_subject": true
    }}
  ],
  "primary_topic": "EU_INTEGRACIJE",
  "primary_topic_confidence": 0.91,
  "topic_explanation": "Clanak izvestava o pregovorima o pristupanju EU i uslovljenosti visa liberalizacijom.",
  "secondary_topics": [
    {{"topic": "POLITIKA", "confidence": 0.67}},
    {{"topic": "MEDIJI_SLOBODA", "confidence": 0.54}}
  ],
  "political_score": 0.72,
  "political_explanation": "Clanak prenosi zvanicne izjave predsednika bez kritickog konteksta i koristi formulacije 'Srbija pobeduje' i 'pritisci Zapada'.",
  "value_score": 0.45,
  "value_explanation": "Naglasava tradicionalne vrednosti i suverenost kao kontraargument evropskim normama.",
  "sensationalism": 0.61,
  "sentiment": "negative",
  "sentiment_score": -0.55,
  "framings": [
    {{"framing_type": "uslovljavanje_frame", "confidence": 0.82, "supporting_text": "...citat iz clanka..."}},
    {{"framing_type": "conflict_frame", "confidence": 0.61, "supporting_text": "...citat iz clanka..."}}
  ],
  "new_framing_proposals": [
    {{"name": "novi_okvir_frame", "description": "Kratak opis okvira", "supporting_text": "...citat..."}}
  ],
  "analysis_confidence": 0.88
}}"""
