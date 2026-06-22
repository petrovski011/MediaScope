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
- Pro-vladini/tabloidni: Informer, Kurir, Blic, Pink, SD, Srbija danas, Prva TV, Tanjug (state-adjacent, privatizovan 2021), RTS (javni servis)
- Nezavisni/opozicioni: N1, Nova, Danas, Radar, Vreme, Insajder, BIRN, Telegraf
- Neutralni/mixes: B92, Mondo, Politika

Politicki kontekst Srbije (Jun 2026):
- Vladajuca stranka: SNS (Aleksandar Vucic, predsednik)
- Kljucni opozicioni akteri: SSP, Srpska stranka Zavetnici, koalicija Srbija protiv nasilja
- Aktuelne teme: EU integracije, medijska sloboda, protesti, infrastrukturni projekti, Kosovo, ekonomija
- Tanjug je privatizovana novinska agencija (2021) sa state-adjacent finansiranjem - njeni tekstovi se preuzimaju na pro-vladinim portalima

Tvoj zadatak je objektivna analiza - ne interpretiras politicke stavove,
vec identifikujes kako mediji izvestavaju i koje narative plasiraju.

Uvek vraci SAMO validan JSON. Nikada ne dodavaj objasnjenja van JSON strukture."""


NARRATIVE_SEED_SYSTEM = """Ti si analiticar narativa za SHARE Fondaciju. Analiziras korpus naslova
srpskih medija i identifikujes DOMINANTNE NARATIVE — ponavljajuce obrasce frejminga koji grade
koherentnu pricu kroz vise tekstova. Narativ je vidljiv tek kroz agregaciju, ne u jednom clanku.
Vracas SAMO validan JSON."""


def build_narrative_seed_prompt(headlines_block: str, n_min: int = 10, n_max: int = 20) -> str:
    """Prompt za inicijalni seeding narativa iz istorijskih naslova."""
    return f"""Analiziras korpus naslova srpskih medijskih clanaka.

Zadatak: identifikuj {n_min}-{n_max} dominantnih narativa.

Narativ definisemo kao:
- Ponavljajuci obrazac frejminga koji gradi koherentnu pricu
- SISTEMSKI (sveobuhvatan, dugorocan, npr. "Srbija kao opkoljena zemlja") ili
  TEMATSKI (vezan za dogadjaj, npr. "Protesti kao strani projekat")
- Vidljiv kroz agregaciju vise tekstova, ne u jednom clanku

NASLOVI (uzorak korpusa):
{headlines_block}

Za svaki narativ navedi: naziv (koncizan), tip (systemic/thematic), opis (2-3 recenice),
i 2-3 primera naslova koji ga ilustruju.

Vrati ISKLJUCIVO JSON:
{{
  "narratives": [
    {{
      "name": "EU kao kolonijalni projekat",
      "type": "systemic",
      "description": "Narativ koji prikazuje EU i zapadne institucije kao silu koja ugrozava suverenitet Srbije.",
      "example_headlines": ["Brisel opet napada Srbiju", "EU hoce da nam diktira"]
    }}
  ]
}}

Fokusiraj se na narative empirijski vidljive u naslovima, ne na teorijske konstrukcije."""


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


def build_narrative_catalog_text(narrative_rows: list[dict]) -> str:
    """Gradi katalog aktivnih VALIDIRANIH narativa za mapiranje.

    narrative_rows: lista {id, name, narrative_type, description}.
    Vazno: model sme da koristi SAMO narrative_id vrednosti iz ovog kataloga.
    """
    if not narrative_rows:
        return ""
    lines = ["KATALOG NARATIVA — mapiraj clanak SAMO na narative iz ove liste (koristi tacan narrative_id).\n"]
    for n in narrative_rows:
        typ = n.get("narrative_type") or "thematic"
        desc = (n.get("description") or "").strip()
        lines.append(f"- id={n['id']} [{typ}] {n['name']}" + (f": {desc}" if desc else ""))
    return "\n".join(lines)


def build_system(
    framing_catalog_text: Optional[str] = None,
    narrative_catalog_text: Optional[str] = None,
    calibration_text: Optional[str] = None,
    enable_caching: bool = True,
):
    """Vraca `system` vrednost za Anthropic poziv.

    Bez dodataka: obican string (SYSTEM_PROMPT).
    Inace: lista blokova [bazni prompt, kalibracija, framing katalog, narativ katalog]
    sa cache_control na poslednjem (identicni kroz ceo batch -> kesiraju se jednom).

    Kalibracija dolazi iz DB (calibration_prompts) — preživljava restart i deli se
    medju workerima (za razliku od ranije in-memory mutacije SYSTEM_PROMPT-a).
    """
    base = SYSTEM_PROMPT
    if calibration_text:
        base = SYSTEM_PROMPT + "\n\n" + calibration_text

    blocks = [{"type": "text", "text": base}]
    if framing_catalog_text:
        blocks.append({"type": "text", "text": framing_catalog_text})
    if narrative_catalog_text:
        blocks.append({"type": "text", "text": narrative_catalog_text})

    if len(blocks) == 1 and not calibration_text:
        return SYSTEM_PROMPT  # nista dodatno -> obican string

    if enable_caching:
        blocks[-1]["cache_control"] = {"type": "ephemeral"}
    return blocks


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
Za svaki entitet oznaci is_political_actor (true ako je politicki akter: funkcioner, stranka,
politicar, drzavna institucija, politicki relevantna organizacija; inace false).
Institucije su UVEK is_political_actor: true — npr. Vlada Srbije, MUP, BIA, REM, Skupstina,
RTS, Predsednistvo, RATEL, tuzilastvo, sudovi kad su akteri politickih odluka.
Genericne grupe NE ukljucuj — samo konkretne i identificirane aktere.
Za svaki entitet proceni SENTIMENT pominjanja (-1.0 negativno, 0.0 neutralno, +1.0 pozitivno):
Kako je konkretno ovaj entitet prikazan u tekstu — kritikovan, podrzan, neutralno opisan?
Ovo je odvojeno od opšteg sentimenta clanka.

## 2. Tematska klasifikacija
Odredi primarnu temu (jednu) i sekundarne (max 3) sa confidence scorovima.
Koristi ove teme: POLITIKA, EU_INTEGRACIJE, KOSOVO, EKONOMIJA, INFRASTRUKTURA,
BEZBEDNOST, MEDIJSKE_SLOBODE, PROTEST, KULTURA, ZABAVA_I_ESTRADA, SPORT, HRONIKA,
ZDRAVLJE, OBRAZOVANJE, SPOLJNA_POLITIKA, LOKALNA_VLAST, DRUSTVO
(KULTURA = pozoriste, film, knjizevnost, klasicna muzika; ZABAVA_I_ESTRADA = rijaliti, celebrity, folk, showbiz)

Ako ne odgovara nijednoj, predlozi novu kao "NOVA_TEMA: NAZIV".

## 3. Politicko pozicioniranje
Proceni na tri ose:

1. POLITICKA OSA (-1.0 do +1.0):
   -1.0 = izrazito opoziciono, 0.0 = neutralno/faktografski, +1.0 = izrazito pro-vladino
   Ovo je objektivna mera stava clanka prema vladajucoj strukturi (SNS/Vucic).
   VAZNO: uzmi u obzir i IMPLICITNO pozicioniranje —
   - Tekst koji velica vladine projekte (Expo, infrastruktura, ekonomski "razvoj", "Srbija napreduje"),
     prenosi vladine izjave bez kritickog konteksta, ili precutkuje kritiku vlasti → pozitivan skor
     cak i kada eksplicitno ne pominje Vucica, SNS ili vladine funkcionere.
   - Tekst koji opisuje vlast kriticno bez imenovanja ("vlast", "rezim", "oni gore") → negativan skor.
   - Neutralan izvestaj bez stava → 0.0.

2. VREDNOSNA OSA (-1.0 do +1.0) — srpski sociokulturni spektar:
   -1.0 = izrazito progresivno (levo):
     podrska LGBT+ pravima i rodnoj ravnopravnosti; sekularizam i razdvajanje crkve i drzave;
     pragmatican pristup Kosovu (dijalog, kompromis, evropski put kao vrednost po sebi);
     pro-EU vrednosti, demokratske norme, vladavina prava; manjinska i nacionalna prava;
     anti-nacionalizam, kosmopolitske vrednosti; feminizam i rodna perspektiva.
   +1.0 = izrazito konzervativno (desno):
     tradicionalne porodicne vrednosti (brak kao zajednica muza i zene, natalitetna politika);
     srpski nacionalizam i etnicka homogenost kao norma; pravoslavlje kao identitetski temelj;
     Kosovo kao neodvojivi deo Srbije bez kompromisa o statusu; skepticizam ili neprijateljstvo
     prema EU/NATO/Zapadu; pro-ruska kulturna ili politicka orijentacija; konzervativni socijalni
     stavovi (anti-gender, protivljenje seksualnoj slobodi, ocuvanje "nasih vrednosti").
   Ocenjuj iskljucivo na osnovu vrednosnih signala u tekstu, ne politicke privrzenosti.

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

## 5b. Propagandne tehnike i smear kampanje
AKTIVNO TRAZI propagandne signale — ne cekaj da budu eksplicitni. Koristi ISKLJUCIVO:
DEMONIZACIJA, DEZINFORMACIJA, CONSPIRACY_THEORY, FEAR_APPEAL, FALSE_DICHOTOMY,
SCAPEGOATING, DEFAMATION, SMEAR_CAMPAIGN, WHATABOUTISM, CHERRY_PICKING, EMOTIONAL_APPEAL,
FAR_RIGHT_NARRATIVE, ULTRA_RIGHT_NARRATIVE.

FAR_RIGHT_NARRATIVE: desnicarski narativ (autoritarnost, etnonacionalizam, anti-liberalizam, anti-EU, "naso coveka").
ULTRA_RIGHT_NARRATIVE: ultradesnicarski narativ (ekstremni nacionalizam, neo-fascisticki elementi, mrznja prema manjinama).
SMEAR_CAMPAIGN / DEFAMATION: posebno detektuj negativne kampanje uperene ka civilnom drustvu/NVO,
opoziciji, studentima/protestima, nezavisnim medijima i novinarima.

propaganda_targets: lista meta — svaki element mora imati:
  - "name": ime entiteta ili grupe (konkretno)
  - "target_group": "civil_society" | "opposition" | "students" | "media" | "other"

Ako nema jasnih propagandnih tehnika — vrati praznu listu.

## 5c. Geopoliticki sentiment
Za sve geopoliticke aktere koji se POMINJU u tekstu, proceni kako ih tekst PRIKAZUJE (ne tvoj licni stav).
Akteri koje pratis: "EU", "Rusija", "SAD", "Kina", "NATO", "Zapad".
Vrati SAMO aktere koji su prisutni u tekstu.
sentiment: -1.0 (izrazito negativan/kritican tretman) do +1.0 (izrazito pozitivan/povoljan tretman), 0.0 = neutralan/faktografski.

## 5. Narativi
Pogledaj KATALOG NARATIVA u sistemskim instrukcijama (ako postoji). Za narative vazi:
- Mapiraj clanak na narative iz kataloga koji su JASNO prisutni. Koristi TACAN narrative_id iz kataloga.
- Jedan clanak moze nositi VISE narativa (sistemski narativi su u pozadini, ne moraju biti eksplicitni).
- Za svaki: narrative_id, confidence (0.0-1.0), kratak citat (supporting_text).
- Ako clanak plasira narativ koji NIJE u katalogu a jasno je prisutan, predlozi ga u "new_narrative_proposals"
  (name, type: "systemic"|"thematic", description, supporting_text).
- Ako katalog ne postoji ili nijedan narativ nije prisutan, vrati praznu listu narratives.

Vrati ISKLJUCIVO ovaj JSON (bez ikakvih objasnjenja van JSON-a):
{{
  "entities": [
    {{
      "name": "Ime Prezime",
      "type": "person",
      "mention_count": 3,
      "has_quote": true,
      "is_main_subject": true,
      "is_political_actor": true,
      "sentiment": 0.3
    }}
  ],
  "primary_topic": "EU_INTEGRACIJE",
  "primary_topic_confidence": 0.91,
  "topic_explanation": "Clanak izvestava o pregovorima o pristupanju EU i uslovljenosti visa liberalizacijom.",
  "secondary_topics": [
    {{"topic": "POLITIKA", "confidence": 0.67}},
    {{"topic": "MEDIJSKE_SLOBODE", "confidence": 0.54}}
  ],
  "political_score": 0.72,
  "political_explanation": "Clanak prenosi zvanicne izjave predsednika bez kritickog konteksta i koristi formulacije 'Srbija pobeduje' i 'pritisci Zapada'.",
  "value_score": 0.45,
  "value_explanation": "Naglasava tradicionalne vrednosti i suverenost kao kontraargument evropskim normama.",
  "sensationalism": 0.61,
  "sentiment": "negative",
  "sentiment_score": -0.55,
  "propaganda_techniques": ["FEAR_APPEAL", "SMEAR_CAMPAIGN"],
  "propaganda_confidence": 0.71,
  "propaganda_targets": [
    {{"name": "Srbija protiv nasilja", "target_group": "opposition"}},
    {{"name": "BIRN", "target_group": "media"}}
  ],
  "geopolitical_sentiment": [
    {{"actor": "EU", "sentiment": -0.6}},
    {{"actor": "Rusija", "sentiment": 0.4}}
  ],
  "framings": [
    {{"framing_type": "uslovljavanje_frame", "confidence": 0.82, "supporting_text": "...citat iz clanka..."}},
    {{"framing_type": "conflict_frame", "confidence": 0.61, "supporting_text": "...citat iz clanka..."}}
  ],
  "new_framing_proposals": [
    {{"name": "novi_okvir_frame", "description": "Kratak opis okvira", "supporting_text": "...citat..."}}
  ],
  "narratives": [
    {{"narrative_id": 3, "confidence": 0.79, "supporting_text": "...citat iz clanka..."}}
  ],
  "new_narrative_proposals": [
    {{"name": "Naziv narativa", "type": "thematic", "description": "Kratak opis", "supporting_text": "...citat..."}}
  ],
  "analysis_confidence": 0.88
}}"""
