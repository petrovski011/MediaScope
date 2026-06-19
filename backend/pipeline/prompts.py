"""
Promptovi za AI pipeline MVP.
MVP obuhvata: NER + Tematska klasifikacija + Politicko pozicioniranje
kombinovano u jedan poziv po clanku.
"""

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
BEZBEDNOST, MEDIJI_SLOBODA, PROTEST, KULTURA_SPORT, HRONIKA,
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
  "secondary_topics": [
    {{"topic": "POLITIKA", "confidence": 0.67}},
    {{"topic": "MEDIJI_SLOBODA", "confidence": 0.54}}
  ],
  "political_score": 0.72,
  "value_score": 0.45,
  "sensationalism": 0.61,
  "sentiment": "negative",
  "sentiment_score": -0.55,
  "analysis_confidence": 0.88
}}"""
