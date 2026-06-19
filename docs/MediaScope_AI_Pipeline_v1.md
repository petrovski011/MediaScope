# MediaScope - AI Pipeline Specifikacija v1.0
**Datum:** Jun 2026 | **SHARE Fondacija**

---

## 1. Pregled i arhitektura

### Princip rada
Pipeline se pokrece kao nocni batch job. Scraper-i prikupljaju clanke tokom dana i noci, a AI pipeline
analizira sve neprocesirane clanke u jednom batch-u koristeci Anthropic Batch API (50% jeftiniji od
standardnog API-ja). Ujutru su rezultati gotovi i dashboard je osvezen.

### Redosled analiticnih koraka
Svaki korak zavisi od prethodnog:

```
1. NER (entiteti)           <- title + subtitle + text
2. Tematska klasifikacija   <- title + subtitle + text + NER rezultati
3. Framing analiza          <- title + text + topic rezultati
4. Politicko pozicioniranje <- title + text + framing rezultati
5. Sentiment                <- title + text
6. Narativno mapiranje      <- sve gornje + postojeci narativi iz DB
7. Koordinacija detekcija   <- uporedjivanje izmedju clanaka (poseban job)
8. Anomalija detekcija      <- statisticka analiza nad svim rezultatima
9. Jutarnji rezime          <- aggregacija svih rezultata
```

Koraci 1-6 se izvrsavaju per-clanak u batch-u.
Koraci 7-9 se izvrsavaju agregacijski, posle batch-a.

### Rasporedivanje
```
22:00 - Scraper-i zavrsavaju poslednji ciklus dana
22:30 - Batch API pozivi se salje za sve nove clanke (koraci 1-6)
02:00 - Batch API rezultati se preuzimaju i upisuju u DB
02:30 - Koordinacija detekcija (korak 7)
03:30 - Anomalija detekcija (korak 8)
04:30 - Generisanje dnevnog intenziteta narativa
05:00 - Jutarnji rezime (korak 9)
06:00 - Dashboard osvezen, istrazivaci vidaju rezultate
```

---

## 2. Token i cost kalkulacija

### Empirijski podaci (iz analize 2.977 clanaka)
- Prosecna duzina teksta: 4.181 znakova = ~1.045 tokena
- Prosecna duzina naslova: 83 znaka = ~21 tokena
- Ukupan prosecni input po clanku: ~1.066 tokena

### Dnevni obim
- Procenjeni prirast: ~1.500 clanaka/dan
- Ukupan input dnevno: 1.500 x ~1.500 tokena (ukljucujuci system prompt): **~2.25M tokena**
- Ukupan output dnevno: 1.500 x ~400 tokena: **~600K tokena**

### Cene (Claude Haiku 4.5 Batch API)
```
Input:  $0.40 / 1M tokena (Batch API, 50% od standardnih $0.80)
Output: $2.00 / 1M tokena (Batch API, 50% od standardnih $4.00)

Dnevno:
  Input:  2.25M x $0.40 = $0.90
  Output: 0.60M x $2.00 = $1.20
  Ukupno: ~$2.10/dan

Mesecno: ~$63/mesec

Sa prompt caching-om (system prompt se kesira):
  Ustedja ~30% na input tokenima
  Realnih: ~$45-50/mesec
```

### Napomena o obliku teksta
Informer i Radar imaju izuzetno dugacke tekstove (~10.000-13.000 znakova). Za ove izvore
tekst se trunkuje na 3.000 reci pre slanja AI-ju - relevantne informacije su u prvoj trecini.

---

## 3. Obrada teksta pre slanja AI-ju

```python
def prepare_article_for_analysis(article: Article) -> dict:
    """
    Priprema clanak za AI analizu.
    Trunkuje preduge tekstove, normalizuje encoding, dodaje kontekst.
    """
    MAX_WORDS = 3000
    MAX_TITLE_CHARS = 300

    title = article.title[:MAX_TITLE_CHARS]
    subtitle = article.subtitle[:200] if article.subtitle else None

    # Trunkuj preduge tekstove (Informer, Radar, Tanjug)
    words = article.text_content.split() if article.text_content else []
    if len(words) > MAX_WORDS:
        text = " ".join(words[:MAX_WORDS]) + "... [tekst trunkovan]"
        truncated = True
    else:
        text = article.text_content or ""
        truncated = False

    return {
        "article_id": article.id,
        "source_id": article.source_id,
        "title": title,
        "subtitle": subtitle,
        "text": text,
        "category": article.category,
        "tags": article.tags or [],
        "published_at": article.published_at.isoformat() if article.published_at else None,
        "truncated": truncated,
        "word_count": len(words),
    }
```

---

## 4. System prompt (deljeni kontekst)

Ovaj system prompt se salje uz svaki API poziv i podleze prompt cachingu.

```
Ti si analiticar medijskog sadrzaja za SHARE Fondaciju, istrazivacku organizaciju
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

Uvek vraci SAMO validan JSON. Nikada ne dodavaj objasnjenja van JSON strukture.
```

---

## 5. Promptovi po koracima

### Korak 1: NER - Prepoznavanje entiteta

**Input:** title, subtitle, text
**Output:** lista entiteta sa tipom i kontekstom

```
Analiziraj sledeci novinarski clanak i identifikuj sve znacajne entitete.

CLANAK:
Izvor: {source_id}
Naslov: {title}
{subtitle_line}
Tekst: {text}

Identifikuj SVE pomenute:
- Osobe (politicians, novinari, javne licnosti, strucnjaci)
- Organizacije (stranke, institucije, kompanije, NGO)
- Mesta (gradovi, regioni, drzave kada su relevantni za kontekst)

Za svaki entitet odredi:
- Da li je direktno citiran (has_quote: true/false)
- Da li je subjekt clanka (is_main_subject: true/false)
- Broj pominjanja

Vrati JSON:
{
  "entities": [
    {
      "name": "Nikola Selaković",
      "type": "person",
      "mention_count": 7,
      "has_quote": true,
      "is_main_subject": true,
      "context": "Ministar kulture koji napada medije zbog izvestavanja o EK izvestaju"
    }
  ]
}

VAZNO:
- Normalizuj varijante istog entiteta (Vucic = Aleksandar Vucic = predsednik Srbije -> koristiti "Aleksandar Vucic")
- Ne ukljucuj genericne pojmove ("vlada", "novinari") - samo konkretne aktere
- Maksimalno 15 entiteta po clanku
```

### Korak 2: Tematska klasifikacija

**Input:** title, subtitle, text, NER rezultati
**Output:** teme sa confidence scorovima

```
Klasifikuj sledeci clanak po temama.

CLANAK:
Izvor: {source_id}
Naslov: {title}
{subtitle_line}
Tekst (prva 500 reci): {text_excerpt}
Kljucni akteri: {entities_summary}

Odredi:
1. Primarna tema (jedna)
2. Sekundarne teme (max 3)
3. Confidence score za svaku temu (0.0-1.0)

Koristi ove teme ili predlozi novu ako ne odgovara nijednoj:
POLITIKA, EU_INTEGRACIJE, KOSOVO, EKONOMIJA, INFRASTRUKTURA,
BEZBEDNOST, MEDIJI_SLOBODA, PROTEST, KULTURA_SPORT, HRONIKA,
ZDRAVLJE, OBRAZOVANJE, SPOLJNA_POLITIKA, LOKALNA_VLAST, DRUSTVO

Vrati JSON:
{
  "primary_topic": "EU_INTEGRACIJE",
  "primary_confidence": 0.91,
  "secondary_topics": [
    { "topic": "MEDIJI_SLOBODA", "confidence": 0.67 },
    { "topic": "POLITIKA", "confidence": 0.54 }
  ],
  "topic_explanation": "Clanak izveštava o EU izvestaju o Srbiji, sa posebnim fokusom na nalaze o medijskim slobodama"
}

Ako tema ne odgovara nijednoj sa liste, predlozi novu:
{
  "primary_topic": "NOVA_TEMA: NUKLEARNA_ENERGIJA",
  ...
}
```

### Korak 3: Framing analiza

**Input:** title, subtitle, text, primary_topic, framing_types_for_topic (iz DB)
**Output:** framing klasifikacija sa objasnjenjima

```
Analiziraj kako sledeci clanak frejmira temu "{primary_topic}".

CLANAK:
Izvor: {source_id}
Naslov: {title}
Tekst: {text}

POZNATI FRAMING TIPOVI ZA OVU TEMU:
{framing_types_json}
(svaki ima: id, name, description)

Zadatak:
1. Odredi koji od poznatih framing tipova se primenjuju u ovom clanku
2. Ako primenjen framing nije na listi, predlozi novi
3. Za svaki framing navedi konkretne delove teksta koji ga podupiru

Framing je NACIN PREDSTAVLJANJA - koje aspekte clanak naglasava,
sta stavlja u prvi plan, kako definise problem i ko je "kriv".
Nije isto sto i politicko pozicioniranje.

Vrati JSON:
{
  "framings": [
    {
      "framing_type_id": 3,
      "framing_name": "Napad na suverenost",
      "confidence": 0.94,
      "is_known": true,
      "supporting_text": [
        "pun lazi i manipulacija",
        "Brisel opet napada Srbiju",
        "politicki nalog"
      ]
    }
  ],
  "new_framing_proposals": [
    {
      "name": "Predlog naziva",
      "description": "Opis novog framing tipa",
      "supporting_text": ["..."]
    }
  ],
  "framing_explanation": "Clanak konsistentno predstavlja EU izvestaj kao neprijateljski cin..."
}
```

### Korak 4: Politicko pozicioniranje

**Input:** title, subtitle, text, framing rezultati
**Output:** skorovi na tri ose

```
Proceni politicko pozicioniranje sledeceg clanka.

CLANAK:
Izvor: {source_id}
Naslov: {title}
Tekst: {text}
Detektovani framing: {framing_summary}

Proceni sledece dimenzije (svaka na skali -1.0 do +1.0 ili 0.0 do 1.0):

1. POLITICKA OSA: Koliko clanak podrzava ili kritikuje vladajucu strukturu (SNS/Vucic)?
   -1.0 = izrazito opoziciono, 0.0 = neutralno, +1.0 = izrazito pro-vladino
   Paznja: Ovo nije procena o "ispravnosti" stava - ovo je objektivna mera kako clanak
   pozicionira vladajucu strukturu.

2. VREDNOSNA OSA: Koji vrednosni okvir clanak zastupa?
   -1.0 = izrazito progresivno, 0.0 = neutralno, +1.0 = izrazito konzervativno

3. SENZACIONALIZAM: Koliko je clanak senzacionalisticki u naslovu i tonu?
   0.0 = potpuno faktografski, 1.0 = izrazito senzacionalisticki

Uzmi u obzir: izbor reci, citiranje izvora, selekciju cinjenica,
naslove i podnaslove, emotivni naboj.

Vrati JSON:
{
  "political_score": 0.87,
  "political_explanation": "Clanak dosljedno frejmira EU kao neprijatelja i brani vladu...",
  "value_score": 0.65,
  "value_explanation": "Konzervativni okvir kroz isticanje nacionalnog suvereniteta...",
  "sensationalism": 0.82,
  "sentiment": "negative",
  "sentiment_score": -0.71,
  "confidence": 0.89
}
```

### Korak 5: Narativno mapiranje

**Input:** title, text, topic, political_score, framing, aktivni narativi iz DB
**Output:** mapiranje na narative + predlozi novih

```
Mapiranje clanka na aktivne narative.

CLANAK:
Izvor: {source_id}
Naslov: {title}
Tema: {primary_topic}
Politicko pozicioniranje: {political_score} (pro-vlada: +1, opozicija: -1)
Framing: {framing_summary}
Tekst (excerpt): {text_excerpt}

AKTIVNI NARATIVI U PLATFORMI:
{narratives_json}
(svaki ima: id, name, type, description)

Zadatak:
1. Odredi koji aktivni narativi su prisutni u ovom clanku
2. Ako clanak plasira narativ koji nije na listi, predlozi novi
3. Sistemski narativi (type: systemic) su sveobuhvatni obrasci
   Tematski narativi (type: thematic) su vezani za konkretan dogadjaj

Vrati JSON:
{
  "narrative_mappings": [
    {
      "narrative_id": 1,
      "narrative_name": "EU kao kolonijalni projekat",
      "narrative_type": "systemic",
      "confidence": 0.89,
      "supporting_text": "Brisel opet napada Srbiju"
    }
  ],
  "new_narrative_proposals": [
    {
      "name": "Predlog naziva narativa",
      "type": "thematic",
      "description": "Opis narativa",
      "evidence": "Ovo je novi narativ jer..."
    }
  ]
}

VAZNO: Jedan clanak moze nositi vise narativa istovremeno.
Sistemski narativi se pojavljuju u pozadini i ne moraju biti eksplicitni.
```

---

## 6. Seeding narativa

Pre pokretanja platforme, potrebno je seeding inicijalnog seta narativa iz istorijskih podataka.

### Seeding prompt

```
Analiziras korpus od {n} srpskih medijskih clanaka objavljenih u periodu {period}.

Zadatak: Identifikuj dominantne narative koji se pojavljuju kroz vise clanaka.

Narativ definisemo kao:
- Ponavljajuci obrazac frejminga koji gradi koherentnu pricu
- Moze biti SISTEMSKI (sveobuhvatan, dugorocan) ili TEMATSKI (vezan za dogadjaj)
- Vidljiv tek kroz agregaciju vise tekstova, ne u jednom clanku

Za svaki narativ navedi:
- Naziv (koncizan, opisuje sustinu)
- Tip (systemic/thematic)
- Opis (2-3 recenice)
- Primeri naslova koji ilustruju narativ
- Koji mediji ga plasiraju
- Procenjenu ucestalost (koliko % clanaka)

CLANCI (agregacija kljucnih naslova i fraza):
{aggregated_headlines_and_phrases}

Vrati JSON:
{
  "narratives": [
    {
      "name": "EU kao kolonijalni projekat",
      "type": "systemic",
      "description": "Narativ koji prikazuje EU i zapadne institucije kao silu koja...",
      "example_headlines": ["Brisel opet napada Srbiju", "EU hoce da nam diktira..."],
      "primary_sources": ["informer", "kurir", "pink"],
      "estimated_frequency_pct": 23,
      "confidence": 0.91
    }
  ]
}

Identifikuj 10-20 narativa. Fokusiraj se na narative koji su empirijski
vidljivi kroz podatke, ne na teorijske konstrukcije.
```

---

## 7. Koordinacija detekcija (batch job)

### 7.1 Copy-paste detekcija

Koristi pgvector cosine similarity umesto AI-ja - jeftinije i preciznije za textualnu slicnost.

```python
async def detect_copypaste(date: date, threshold: float = 0.85):
    """
    Uporedjuje sve clanke objavljene u 48h prozoru.
    Koristi pgvector cosine similarity na embeddingima.
    Jeftinije i preciznije od AI-ja za ovu vrstu detekcije.
    """
    # 1. Dohvati sve clanke sa embeddingima za zadati period
    # 2. SQL: SELECT a1.id, a2.id, (a1.embedding <=> a2.embedding) as distance
    #         FROM article_embeddings a1, article_embeddings a2
    #         WHERE a1.article_id != a2.article_id
    #           AND a1.article_id < a2.article_id
    #           AND (1 - (a1.embedding <=> a2.embedding)) > threshold
    # 3. Upisi u coordination_copypaste
    # 4. Kreiraj alertove za parove sa score > 0.92
    pass
```

### 7.2 Framing koordinacija (AI)

```
Analiziraj potencijalnu framing koordinaciju izmedju medija.

PODATAK: Sledeci mediji su koristili framing tip "{framing_name}"
za temu "{topic}" u vremenskom prozoru od {hours}h:

{articles_by_source}

Svaki unos sadrzi: source_id, published_at, naslov, kljucne fraze

Odredi:
1. Da li postoji koordinacija ili je to prirodno poklapanje?
2. Koji je smer - ko je inicirao?
3. Koji su signali koordinacije (specificne fraze, isti naglasci)?

Koordinacija je SUMNJIVA ako:
- Vise medija razlicite vlasnicke grupe koristi identicne fraze
- Vremenski sled je kratak (<2h) i sistematican
- Isti neobicni ugao pristupa pojavljuje se kod vise izvora

Vrati JSON:
{
  "coordination_score": 0.87,
  "is_suspicious": true,
  "coordination_type": "synchronized_framing",
  "initiator_source": "informer",
  "signals": [
    "Identična fraza 'politički nalog' u 3 naslova u roku od 45 minuta",
    "Isti neobicni ugao: fokus na 'suverenost' umesto na konkretne nalaze"
  ],
  "same_owner_group": false,
  "confidence": 0.84
}
```

### 7.3 Narativna koordinacija (AI)

```
Analiziraj narativnu koordinaciju za narativ "{narrative_name}".

PODATAK: Sledeci mediji su plasirali ovaj narativ u vremenskom prozoru {hours}h:

{articles_summary_by_source}

Odredi nivo narativne koordinacije.

Za razliku od framing koordinacije, narativna koordinacija je suptilnija -
mediji ne moraju deliti iste fraze, vec grade istu koherentnu pricu
kroz razlicite naslove i uglove.

Vrati JSON:
{
  "coordination_score": 0.91,
  "is_suspicious": true,
  "evidence": "...",
  "same_owner_group": false,
  "confidence": 0.88
}
```

---

## 8. Anomalija detekcija (statisticki job)

Ovo je Python/SQL job, ne AI prompt - jeftiniji i brzi.

```python
async def detect_anomalies(date: date):
    """
    Detektuje statisticke anomalije u pokrivnosti tema, framing promenama i narativima.
    Poredi sa rolling baseline (7d i 30d).
    """

    # 1. Topic spike/drop
    # Za svaku temu poredi danasnji broj clanaka sa 7d i 30d prosekom
    # Anomalija: odstupanje > 200% od baseline

    # 2. Framing shift
    # Za svaku temu poredi distribuciju framing tipova danas vs. 7d prosek
    # Anomalija: dominantni framing se promeni za > 30 procentnih poena

    # 3. Silence anomalija
    # Teme koje je medij pokrivao prosle nedelje a nije danas
    # Samo za izvore koji imaju > 5 clanaka/dan

    # 4. Narativ koji nestaje/jaca naglo
    # Poredi dnevni intenzitet narativa sa 7d prosekom
    # Anomalija: promena > 150%

    # 5. Sync anomalija
    # Neuobicajena sinhronizacija izmedju medija koji inace ne koordinisu
    # Ulaz: coordination scores iz coordination tabela
    pass
```

---

## 9. Jutarnji rezime

```
Ti si analiticar medija koji pise dnevni rezime za istrazivacki tim SHARE Fondacije.

PODACI ZA {date}:

Opsti pregled:
- Ukupno clanaka: {article_count} (promena: {change_pct}% vs juče)
- Aktivnih narativa: {active_narratives}
- Koordinacija alertova: {coordination_alerts}
- Anomalija: {anomaly_count}

Top teme po pokrivenosti:
{top_topics}

Aktivni narativi (intenzitet danas vs. juče):
{narratives_with_changes}

Koordinacija alertovi:
{coordination_alerts_detail}

Anomalije:
{anomalies_detail}

Napisi executive summary od 4-6 recenica koji:
1. Identifikuje dominantnu temu dana
2. Naglasava kljucnu razliku u izvestavanju izmedju pro-vladinih i nezavisnih medija
3. Pominje najznacajniji koordinacioni ili narativni dogadjaj
4. Ukazuje na eventualne anomalije (silence, nagli shift)

Ton je objektivan i analiticni. Izbegavaj vrednosne sudove.
Pisi u trece lice. Maksimalno 150 reci.

Vrati JSON:
{
  "summary_text": "Dominantna tema proteklog dana bila je...",
  "key_insight": "Kljucni nalaz jednom recenicom",
  "alert_level": "high|medium|low",
  "top_topics": [...],
  "top_narratives": [...]
}
```

---

## 10. Kalibracija i RLHF

### Kalibracioni prompt mehanizam

Svaki feedback istrazivaca se integrise u kalibracioni prompt koji se dodaje uz system prompt:

```
KALIBRACIONI KONTEKST (na osnovu feedback istrazivaca):

POLITICKO POZICIONIRANJE - korigovanim primerima:
- Clanci koji citiraju opoziciju neutralno (bez vrednosnog suda) treba da dobiju
  skor blizu 0.0, ne negativan skor. Primer: [excerpt]
- Tanjug clanci su neutralni po defaultu osim ako eksplicitno brane vladu. Primer: [excerpt]

TEMATSKA KLASIFIKACIJA - greske koje treba izbegavati:
- Sportske vesti o reprezentaciji nisu POLITIKA cak i ako sadrze izjave predsednika
- Ekonomske analize sa politickim kontekstom idu u EKONOMIJA, ne POLITIKA

FRAMING - preciziranje:
- "Neutralni prikaz" znaci faktualno izvestavanje bez evaluativnih fraza
  Nije dovoljno sto clanak ne napada opoziciju - mora i aktivno da ne brani vladu

[novi primeri se dodaju automatski na osnovu feedback-a]
```

### Workflow kalibracije

```python
async def apply_calibration(analysis_type: str, feedback_ids: list[int]):
    """
    Primenjuje feedback na kalibracioni prompt.
    Pokrece re-analizu clanaka slicnih onima koji su korigovani.
    """
    # 1. Dohvati feedbacke
    # 2. Grupiši po analiza_type
    # 3. Generiši novi kalibracioni kontekst kroz AI
    # 4. Sacuvaj kao novi prompt u calibration_prompts tabeli
    # 5. Oznaci feedbacke kao applied_to_pipeline=True
    # 6. Pokreni re-analizu za clankove slicne korigovanim (embedding similarity)

    REANALYSIS_PROMPT = """
    Na osnovu novog kalibracionog konteksta, re-analiziraj sledece clanke.
    Posebno obrati paznju na korekcije opisane u kalibracionom kontekstu.

    [kalibracioni kontekst]
    [clanci za re-analizu]
    """
    pass
```

---

## 11. Embedding generisanje

Embeddinzi se koriste za:
1. Copy-paste detekcija (cosine similarity)
2. "Slicni clanci" feature u UI-u
3. Pronalazenje clanaka za re-analizu pri kalibraciji

```python
async def generate_embeddings_batch(article_ids: list[int]):
    """
    Generise embeddinze za listu clanaka.
    Koristi Anthropic embeddings API ili OpenAI text-embedding-3-small.
    Dimenzija: 1536 (OpenAI) ili 1024 (Anthropic Voyage)
    """
    # Input za embedding: title + " " + text[:1000]
    # Kratko - dovoljno za semanticku slicnost, ne treba ceo tekst
    pass
```

**Preporuka:** Anthropic Voyage API (voyage-3-lite) je optimizovan za dugacke dokumente
i jeftiniji od OpenAI. Dimenzija 512 je dovoljna za copy-paste detekciju.

---

## 12. Error handling i retry logika

```python
BATCH_API_CONFIG = {
    "max_tokens_per_request": 2000,
    "retry_attempts": 3,
    "retry_delay_seconds": [30, 120, 300],
    "timeout_hours": 24,        # Batch API moze da traje do 24h
    "check_interval_minutes": 15,
}

# Tipovi gresaka i handling:
# - RATE_LIMIT: sacekaj i retry
# - CONTEXT_LENGTH: skrati tekst i retry
# - INVALID_JSON: retry sa striktijim JSON instrukcijama
# - API_ERROR: log i skip (clanak ce biti analiziran sutra)
# - TIMEOUT: proveri batch status, restart ako je stuck
```

---

## 13. Pracenje kolicine i logging

```python
PIPELINE_METRICS = {
    "articles_analyzed": 0,
    "articles_failed": 0,
    "new_entities_detected": 0,
    "new_framing_proposals": 0,
    "new_narrative_proposals": 0,
    "total_input_tokens": 0,
    "total_output_tokens": 0,
    "estimated_cost_usd": 0.0,
    "pipeline_duration_minutes": 0,
}
```

---

## 14. Konfiguracioni parametri

```python
# settings.py - AI Pipeline

ANTHROPIC_MODEL = "claude-haiku-4-5"
ANTHROPIC_BATCH_MODE = True

# Pragovi
COPYPASTE_THRESHOLD = 0.85          # cosine similarity za copy-paste
FRAMING_COORD_MIN_SCORE = 0.70      # min skor za framing koordinaciju alert
NARRATIVE_COORD_MIN_SCORE = 0.75    # min skor za narativni koordinacija alert
ANOMALY_DEVIATION_THRESHOLD = 2.0  # 200% od baseline = anomalija
NARRATIVE_INTENSITY_THRESHOLD = 0.30 # min intenzitet da se pojavi na dashboardu

# Tekst limiti
MAX_TEXT_WORDS = 3000               # trunkovanje pred AI
MAX_TITLE_CHARS = 300
MAX_ENTITIES_PER_ARTICLE = 15
MAX_FRAMINGS_PER_ARTICLE = 5
MAX_NARRATIVES_PER_ARTICLE = 5

# Intraday iskljuceni izvori (bez tacnog vremena)
INTRADAY_EXCLUDED_SOURCES = ["rts", "tanjug"]

# Baseline prozori za anomalije
ANOMALY_BASELINE_SHORT = 7         # dana
ANOMALY_BASELINE_LONG = 30         # dana

# Jutarnji rezime
MORNING_SUMMARY_HOUR = 5            # 05:00
MORNING_SUMMARY_MAX_WORDS = 150
```

---

## 15. Prioritet implementacije

### Faza 1 - MVP (za pocetno testiranje)
1. NER + Tematska klasifikacija + Politicko pozicioniranje
2. Copy-paste detekcija (pgvector, bez AI)
3. Jutarnji rezime

### Faza 2 - Core analitika
4. Framing analiza
5. Seeding narativa iz istorijskih podataka
6. Narativno mapiranje
7. Anomalija detekcija (statisticki job)

### Faza 3 - Koordinacija i kalibracija
8. Framing koordinacija detekcija (AI)
9. Narativna koordinacija detekcija (AI)
10. Kalibracija RLHF workflow

### Faza 4 - Optimizacija
11. Embedding generisanje za similarity features
12. Prompt caching optimizacija
13. Cost monitoring i alerting
