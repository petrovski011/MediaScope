# MediaScope - FastAPI Specifikacija v1.0
**Datum:** Jun 2026 | **SHARE Fondacija**

---

## 1. Arhitektura i konvencije

### Stack
- **Framework:** FastAPI (Python 3.11+)
- **ORM:** SQLAlchemy 2.0 (async) + Alembic za migracije
- **DB:** PostgreSQL 16
- **Auth:** JWT (python-jose) + bcrypt za lozinke
- **Background jobs:** APScheduler (scraper scheduler) + Celery (AI batch pipeline)
- **Cache:** Redis (rate limiting, session cache, query cache za dashboard)
- **Validation:** Pydantic v2

### Konvencije
- Sve rute prefixovane sa `/api/v1/`
- Autentikacija: `Authorization: Bearer <token>` header
- Paginacija: `?page=1&per_page=20` (default per_page=20, max=100)
- Datumi: ISO8601 sa timezone (`2026-06-18T14:32:00+02:00`)
- Greske: `{"detail": "poruka", "code": "ERROR_CODE"}`
- Soft filtering: `?source_ids=n1,blic&date_from=2026-06-01&date_to=2026-06-18`

### Role i permisije
```
viewer     -> GET rute za dashboard, clanke, analize, narative
researcher -> sve od viewer + POST za feedback, watchliste, sacuvane pretrage
admin      -> sve od researcher + upravljanje korisnicima, izvorima, re-analiza
```

---

## 2. Autentikacija

### POST /api/v1/auth/login
```json
Request:
{ "email": "andrej@sharefoundation.info", "password": "..." }

Response 200:
{
  "access_token": "eyJ...",
  "token_type": "bearer",
  "expires_in": 86400,
  "user": {
    "id": 1,
    "email": "andrej@sharefoundation.info",
    "name": "Andrej Petrovic",
    "role": "admin"
  }
}

Errors: 401 INVALID_CREDENTIALS
```

### POST /api/v1/auth/refresh
```json
Request: { "token": "eyJ..." }
Response 200: { "access_token": "eyJ...", "expires_in": 86400 }
```

### GET /api/v1/auth/me
```json
Response 200:
{
  "id": 1,
  "email": "...",
  "name": "...",
  "role": "admin",
  "last_login": "2026-06-18T06:14:00+02:00"
}
```

---

## 3. Dashboard

### GET /api/v1/dashboard/summary
**Opis:** Glavni dashboard endpoint - sve sto treba za jutarnji pregled.
**Auth:** viewer+
**Query params:** `date` (default: danas)

```json
Response 200:
{
  "date": "2026-06-18",
  "period": {
    "date_from": "2026-06-18T00:00:00+02:00",
    "date_to": "2026-06-18T23:59:59+02:00"
  },
  "metrics": {
    "articles_today": 1847,
    "articles_change_pct": 12.4,
    "active_narratives": 23,
    "new_narratives_7d": 3,
    "coordination_alerts": 4,
    "coordination_alerts_change": 2,
    "sources_active": 19,
    "sources_total": 20
  },
  "morning_summary": {
    "text": "Dominantna tema proteklog dana bila je...",
    "generated_at": "2026-06-18T06:14:00+02:00",
    "model_used": "claude-haiku-4-5"
  },
  "alerts": [...],       // top 3 alerta, vidi /alerts
  "top_narratives": [...], // top 5 narativa, vidi /narratives
  "top_topics": [...],
  "political_scores": {  // top 5 pro-vlada i top 5 opozicija
    "pro_government": [...],
    "opposition": [...]
  },
  "topic_coverage": [...]  // top teme sa brojem medija koji pokrivaju
}
```

### GET /api/v1/dashboard/metrics/timeseries
**Opis:** Vremenska serija metrika za grafove na dashboardu.
**Query params:** `metric` (articles|narratives|alerts|political_score), `source_ids`, `date_from`, `date_to`, `granularity` (day|hour)

```json
Response 200:
{
  "metric": "articles",
  "granularity": "day",
  "series": [
    { "timestamp": "2026-06-17T00:00:00+02:00", "value": 1654 },
    { "timestamp": "2026-06-18T00:00:00+02:00", "value": 1847 }
  ]
}
```

---

## 4. Clanci

### GET /api/v1/articles
**Opis:** Lista clanaka sa filterima. Osnova za pretragu i analizu.
**Auth:** viewer+
**Query params:**
- `source_ids` - lista source_id razdvojena zarezima
- `date_from`, `date_to` - ISO8601
- `topic` - filtriranje po temi
- `narrative_id` - filtriranje po narrativu
- `political_score_min`, `political_score_max` - -1.0 do 1.0
- `has_analysis` - boolean, samo clanci sa AI analizom
- `search` - fulltext pretraga po naslovu i tekstu
- `page`, `per_page`
- `sort` (published_at|scraped_at|political_score|sensationalism), `order` (asc|desc)

```json
Response 200:
{
  "total": 2977,
  "page": 1,
  "per_page": 20,
  "pages": 149,
  "items": [
    {
      "id": 12345,
      "source_id": "informer",
      "source_name": "Informer",
      "owner_group": "Domaci privatni",
      "url": "https://informer.rs/...",
      "title": "Brisel opet napada Srbiju",
      "subtitle": "Izvestaj EK je politicki nalog",
      "word_count": 2004,
      "author": "Redakcija politike",
      "published_at": "2026-06-18T14:32:00+02:00",
      "category": "politika",
      "tags": ["EU", "Selaković", "izvestaj"],
      "image_url": "https://...",
      "has_analysis": true,
      "analysis_summary": {
        "primary_topic": "EU integracije",
        "political_score": 0.94,
        "value_score": 0.71,
        "sensationalism": 0.87,
        "sentiment": "negative"
      }
    }
  ]
}
```

### GET /api/v1/articles/{id}
**Opis:** Detaljan prikaz jednog clanka sa kompletnom AI analizom.
**Auth:** researcher+ (raw tekst), viewer (samo meta)

```json
Response 200:
{
  "id": 12345,
  "source_id": "informer",
  "source_name": "Informer",
  "url": "...",
  "title": "...",
  "subtitle": "...",
  "text_content": "...",   // samo za researcher+
  "word_count": 2004,
  "author": "...",
  "published_at": "...",
  "updated_at": null,
  "category": "politika",
  "tags": [...],
  "image_url": "...",
  "version": 1,
  "scraped_at": "...",
  "analysis": {
    "topics": ["EU integracije", "medijska sloboda"],
    "primary_topic": "EU integracije",
    "topic_confidence": 0.91,
    "political_score": 0.94,
    "political_explanation": "Tekst konsistentno frejmira EU kao pretnju...",
    "value_score": 0.71,
    "value_explanation": "Konzervativni okvir kroz pozivanje na suverenost...",
    "sensationalism": 0.87,
    "sentiment": "negative",
    "sentiment_score": -0.72,
    "analyzed_at": "2026-06-18T06:20:00+02:00",
    "model_used": "claude-haiku-4-5"
  },
  "entities": [
    {
      "id": 42,
      "name": "Nikola Selaković",
      "entity_type": "person",
      "is_political_actor": true,
      "mention_count": 7,
      "is_quoted": true,
      "is_subject": true
    }
  ],
  "framings": [
    {
      "framing_type_id": 3,
      "framing_name": "Napad na suverenost",
      "confidence": 0.94,
      "supporting_text": "...pun lazi i manipulacija..."
    }
  ],
  "narratives": [
    {
      "narrative_id": 1,
      "narrative_name": "EU kao kolonijalni projekat",
      "narrative_type": "systemic",
      "confidence": 0.89
    }
  ],
  "versions": [
    { "version": 1, "changed_at": "...", "changed_fields": [] }
  ]
}
```

### GET /api/v1/articles/{id}/versions
**Auth:** researcher+
Vraca istoriju verzija clanka.

### POST /api/v1/articles/{id}/feedback
**Auth:** researcher+
**Opis:** RLHF feedback za kalibraciju AI analize.

```json
Request:
{
  "analysis_type": "political_score",  // topic|framing|narrative|political_score|value_score
  "is_correct": false,
  "comment": "Ovo nije pro-vladinski - clanak je neutralno izvestavanje",
  "corrected_value": "0.1"
}

Response 201:
{ "id": 88, "applied_to_pipeline": false, "message": "Feedback sacuvan" }
```

---

## 5. Mediji (Sources)

### GET /api/v1/sources
**Auth:** viewer+

```json
Response 200:
{
  "items": [
    {
      "source_id": "informer",
      "name": "Informer",
      "url": "https://informer.rs",
      "owner": "Dragan J. Vucicevic",
      "owner_group": "Domaci privatni",
      "media_type": "portal",
      "is_active": true,
      "has_timestamp_time": true,
      "has_author": true,
      "stats": {
        "articles_total": 99,
        "articles_today": 12,
        "last_scraped": "2026-06-18T11:30:00+02:00",
        "avg_political_score": 0.91,
        "avg_value_score": 0.68,
        "avg_sensationalism": 0.84
      }
    }
  ]
}
```

### GET /api/v1/sources/{source_id}
**Opis:** Detaljan profil medija sa evolucijom skora.

```json
Response 200:
{
  "source_id": "informer",
  "name": "Informer",
  ...
  "score_history": [
    { "date": "2026-06-17", "political_score": 0.90, "sensationalism": 0.85, "article_count": 47 },
    { "date": "2026-06-18", "political_score": 0.91, "sensationalism": 0.84, "article_count": 42 }
  ],
  "top_topics": ["politika", "EU", "protest"],
  "top_entities": [...],
  "active_narratives": [...],
  "active_framings": [...]
}
```

### GET /api/v1/sources/{source_id}/articles
Vraca clanke za jedan izvor. Iste query params kao /articles.

### GET /api/v1/sources/comparison
**Opis:** Uporedjivanje vise medija po razlicitim metrikama.
**Query params:** `source_ids` (obavezno), `metric` (political_score|sensationalism|topic_coverage), `date_from`, `date_to`

```json
Response 200:
{
  "sources": ["informer", "n1", "rts"],
  "metric": "political_score",
  "date_from": "2026-06-01",
  "date_to": "2026-06-18",
  "series": {
    "informer": [...],
    "n1": [...],
    "rts": [...]
  }
}
```

---

## 6. Teme

### GET /api/v1/topics
**Auth:** viewer+
**Query params:** `date_from`, `date_to`, `source_ids`

```json
Response 200:
{
  "items": [
    {
      "topic": "EU integracije",
      "article_count": 347,
      "source_count": 18,
      "sources_covering": ["n1", "informer", "rts", ...],
      "sources_silent": ["sd"],
      "date_first": "2026-06-15",
      "date_last": "2026-06-18",
      "dominant_framing": "Napad na suverenost",
      "framing_split": {
        "Napad na suverenost": 0.47,
        "Merilo demokratskog napretka": 0.31,
        "Neutralni prikaz": 0.22
      }
    }
  ]
}
```

### GET /api/v1/topics/{topic}/coverage
**Opis:** Matrica pokrivenosti teme po medijima - osnova za agenda-setting i silence analizu.

```json
Response 200:
{
  "topic": "EU integracije",
  "date_from": "...",
  "date_to": "...",
  "coverage": [
    {
      "source_id": "informer",
      "source_name": "Informer",
      "article_count": 42,
      "dominant_framing": "Napad na suverenost",
      "political_score_avg": 0.91,
      "first_article_at": "2026-06-15T09:12:00+02:00"
    },
    {
      "source_id": "juzne",
      "source_name": "Juzne vesti",
      "article_count": 0,
      "is_silent": true
    }
  ]
}
```

### GET /api/v1/topics/{topic}/framing
**Opis:** Framing analiza za specificnu temu.

```json
Response 200:
{
  "topic": "EU integracije",
  "framing_types": [
    {
      "id": 3,
      "name": "Napad na suverenost",
      "article_count": 163,
      "pct": 0.47,
      "sources": ["informer", "kurir", "pink", "alo", "prva"],
      "owner_groups": ["Domaci privatni", "Adria Media", "Pink Media Group"]
    }
  ],
  "framing_by_source": {
    "informer": { "Napad na suverenost": 38, "Neutralni prikaz": 4 },
    "n1": { "Merilo demokratskog napretka": 22, "Neutralni prikaz": 6 }
  }
}
```

---

## 7. Framing

### GET /api/v1/framing/types
**Auth:** viewer+
**Query params:** `topic`, `is_validated`

```json
Response 200:
{
  "items": [
    {
      "id": 3,
      "name": "Napad na suverenost",
      "topic": "EU integracije",
      "description": "...",
      "is_validated": true,
      "article_count": 163,
      "created_by": "AI predlog",
      "created_at": "2026-06-15"
    }
  ]
}
```

### POST /api/v1/framing/types
**Auth:** researcher+
**Opis:** Kreiranje custom framing tipa.

```json
Request:
{
  "name": "Klijentisticki okvir",
  "topic": "medijska sloboda",
  "description": "Mediji kao deo finansijsko-politickog mehanizma"
}
Response 201: { "id": 12, ... }
```

### PUT /api/v1/framing/types/{id}/validate
**Auth:** researcher+
Potvrda AI predloga framing tipa.

### GET /api/v1/framing/evolution
**Opis:** Evolucija framing tipova kroz vreme za datu temu.
**Query params:** `topic` (obavezno), `date_from`, `date_to`, `source_ids`

```json
Response 200:
{
  "topic": "protesti",
  "series": [
    {
      "date": "2026-06-10",
      "framings": {
        "Huliganstvo": 0.61,
        "Demokratski protest": 0.28,
        "Strani projekat": 0.11
      }
    }
  ]
}
```

---

## 8. Narativi

### GET /api/v1/narratives
**Auth:** viewer+
**Query params:** `narrative_type` (systemic|thematic), `is_active`, `is_validated`, `date_from`, `date_to`

```json
Response 200:
{
  "items": [
    {
      "id": 1,
      "name": "EU kao kolonijalni projekat",
      "narrative_type": "systemic",
      "is_active": true,
      "is_validated": true,
      "article_count_today": 47,
      "article_count_7d": 312,
      "intensity_today": 0.92,
      "intensity_change_pct": 34.0,
      "top_sources": ["informer", "kurir", "pink"],
      "detected_at": "2026-06-01"
    }
  ]
}
```

### GET /api/v1/narratives/{id}
**Opis:** Detaljan prikaz narativa sa evolucijom.

```json
Response 200:
{
  "id": 1,
  "name": "EU kao kolonijalni projekat",
  "narrative_type": "systemic",
  "description": "...",
  "intensity_history": [
    { "date": "2026-06-10", "intensity": 0.71, "article_count": 28 },
    { "date": "2026-06-18", "intensity": 0.92, "article_count": 47 }
  ],
  "intensity_by_source": {
    "informer": [...],
    "n1": [...]
  },
  "top_articles": [...],
  "related_framings": [...],
  "related_entities": [...]
}
```

### GET /api/v1/narratives/{id}/articles
Clanci mapirani na narativ. Iste query params kao /articles.

### POST /api/v1/narratives/{id}/validate
**Auth:** researcher+
Validacija AI predloga narativa.

### POST /api/v1/narratives
**Auth:** researcher+
Kreiranje custom narativa.

### GET /api/v1/narratives/intraday
**Auth:** viewer+
**Opis:** Distribucija narativa po satu za dati dan. Iskljucuje RTS i Tanjug.
**Query params:** `date` (default: juče), `narrative_ids`, `source_ids`

```json
Response 200:
{
  "date": "2026-06-18",
  "note": "RTS i Tanjug iskljuceni zbog nedostajuceg vremena u timestampu",
  "excluded_sources": ["rts", "tanjug"],
  "series": [
    {
      "hour": 6,
      "narratives": {
        "EU kao kolonijalni projekat": 3,
        "Srbija kao garant stabilnosti": 1
      }
    }
  ]
}
```

### GET /api/v1/narratives/weekly-summary
**Auth:** viewer+
**Query params:** `week_start` (ISO date, default: prethodna nedelja)
AI generisani nedeljni presek narativa.

---

## 9. Koordinacija

### GET /api/v1/coordination/alerts
**Auth:** viewer+
**Query params:** `coordination_type` (copypaste|framing|narrative), `date_from`, `date_to`, `min_score`, `source_ids`

```json
Response 200:
{
  "items": [
    {
      "id": 77,
      "coordination_type": "narrative",
      "score": 0.94,
      "sources": ["informer", "kurir", "pink"],
      "same_owner_group": false,
      "narrative_name": "EU kao kolonijalni projekat",
      "date": "2026-06-18",
      "hour_window": 3,
      "article_count": 7,
      "description": "Narativna koordinacija izmedju razlicitih vlasnickih grupa u prozoru 18-21h"
    }
  ]
}
```

### GET /api/v1/coordination/alerts/{id}
**Opis:** Detalj alerta sa konkretnim clancima.

```json
Response 200:
{
  "id": 77,
  ...
  "articles": [
    {
      "id": 12345,
      "source_id": "informer",
      "title": "Brisel opet napada Srbiju",
      "published_at": "2026-06-18T18:47:00+02:00",
      "political_score": 0.94
    }
  ],
  "methodology_note": "Koordinacija detektovana izmedju razlicitih vlasnickih grupa. Interpretacija ostaje na istrazivacu."
}
```

### GET /api/v1/coordination/network
**Opis:** Graf veza izmedju medija zasnovan na koordinaciji.
**Query params:** `date_from`, `date_to`, `coordination_type`, `min_score`

```json
Response 200:
{
  "nodes": [
    { "id": "informer", "name": "Informer", "owner_group": "Domaci privatni", "alert_count": 7 }
  ],
  "edges": [
    {
      "source": "informer",
      "target": "kurir",
      "weight": 0.87,
      "coordination_types": ["copypaste", "narrative"],
      "same_owner_group": false
    }
  ]
}
```

### GET /api/v1/coordination/copypaste
**Opis:** Copy-paste parovi sortovani po similarity skoru.
**Query params:** `min_score` (default: 0.8), `date_from`, `date_to`, `source_ids`

```json
Response 200:
{
  "items": [
    {
      "article_a": { "id": 123, "source_id": "kurir", "title": "...", "published_at": "..." },
      "article_b": { "id": 456, "source_id": "sd", "title": "...", "published_at": "..." },
      "similarity_score": 0.94,
      "same_owner_group": false,
      "time_diff_minutes": 23
    }
  ]
}
```

---

## 10. Anomalije

### GET /api/v1/anomalies
**Auth:** viewer+
**Query params:** `anomaly_type`, `source_id`, `date_from`, `date_to`

```json
Response 200:
{
  "items": [
    {
      "id": 12,
      "anomaly_type": "topic_spike",
      "description": "Nagli rast pokrivenosti teme 'EU integracije' - +340% vs. rolling 7d baseline",
      "source_id": null,
      "topic": "EU integracije",
      "date": "2026-06-18",
      "baseline_value": 12.4,
      "detected_value": 54.6,
      "deviation_pct": 340.3,
      "baseline_type": "rolling_7d"
    }
  ]
}
```

---

## 11. Origin tracking

### GET /api/v1/origin
**Auth:** viewer+
**Query params:** `topic`, `date_from`, `date_to`

```json
Response 200:
{
  "items": [
    {
      "id": 5,
      "topic": "EU integracije - izvestaj EK",
      "first_source_id": "tanjug",
      "first_source_name": "Tanjug",
      "first_published_at": "2026-06-15",
      "has_exact_time": false,
      "note": "Tanjug nema tacno vreme objave - datum je pouzdan, sat nije",
      "total_coverage": 18,
      "spread_hours": null,
      "narrative_name": "EU kao kolonijalni projekat",
      "spread_timeline": [
        { "source_id": "tanjug", "published_at": "2026-06-15", "exact_time": false },
        { "source_id": "rts", "published_at": "2026-06-15", "exact_time": false },
        { "source_id": "informer", "published_at": "2026-06-15T09:12:00+02:00", "exact_time": true }
      ]
    }
  ]
}
```

---

## 12. Politicka analiza

### GET /api/v1/political/actors
**Auth:** viewer+
**Query params:** `date_from`, `date_to`, `source_ids`, `min_mentions`

```json
Response 200:
{
  "items": [
    {
      "entity_id": 1,
      "name": "Aleksandar Vucic",
      "entity_type": "person",
      "total_mentions": 847,
      "quoted_count": 312,
      "subject_count": 203,
      "coverage_by_alignment": {
        "pro_government": { "mention_count": 712, "avg_sentiment": 0.6 },
        "opposition": { "mention_count": 287, "avg_sentiment": -0.4 },
        "neutral": { "mention_count": 91, "avg_sentiment": 0.1 }
      }
    }
  ]
}
```

### GET /api/v1/political/narrative-origin
**Opis:** Smer kauzalnosti - da li narativ krece od aktera ka medijima ili obrnuto.
**Query params:** `narrative_id`, `entity_id`, `date_from`, `date_to`

```json
Response 200:
{
  "narrative_id": 1,
  "narrative_name": "EU kao kolonijalni projekat",
  "direction": "actor_to_media",
  "confidence": 0.85,
  "description": "Izjava Vucica (14. jun) - preuzeto za 4h u 8 pro-vladinih medija",
  "methodology_note": "Interpretacija ostaje na istrazivacu"
}
```

### GET /api/v1/political/meta-framing
**Opis:** Detekcija populistickog meta-framinga narod vs. elite.
**Query params:** `date_from`, `date_to`, `source_ids`

```json
Response 200:
{
  "period": { "from": "...", "to": "..." },
  "meta_framing_pct": 0.34,
  "by_source": {
    "informer": 0.61,
    "n1": 0.18,
    "rts": 0.22
  },
  "note": "Meta-framing prisutan i u pro-vladinom i u opozicionom diskursu"
}
```

---

## 13. Pretraga

### GET /api/v1/search
**Auth:** viewer+
**Query params:**
- `q` - fulltext query (obavezno ako nema ostalih filtera)
- `source_ids`, `date_from`, `date_to`
- `entity_id`, `entity_name`
- `topic`
- `narrative_id`
- `framing_type_id`
- `political_score_min`, `political_score_max`
- `has_analysis`
- `page`, `per_page`
- `sort`, `order`

```json
Response 200:
{
  "total": 847,
  "query": "Selaković",
  "filters_applied": ["source_ids", "date_from"],
  "page": 1,
  "per_page": 20,
  "items": [...]   // ArticleListItem format kao u /articles
}
```

---

## 14. Moj prostor (Watchliste i sacuvane pretrage)

### GET /api/v1/watchlists
**Auth:** researcher+

### POST /api/v1/watchlists
```json
Request:
{
  "name": "Pracenje slobode medija",
  "description": "...",
  "items": [
    { "item_type": "source", "item_id": "birn" },
    { "item_type": "entity", "item_id": 42 },
    { "item_type": "topic", "item_value": "sloboda medija" },
    { "item_type": "narrative", "item_id": 5 }
  ]
}
Response 201: { "id": 3, ... }
```

### GET /api/v1/watchlists/{id}/feed
**Opis:** Feed novih clanaka i alertova relevantnih za watchlistu.
**Query params:** `date_from`, `date_to`, `page`, `per_page`

### POST /api/v1/saved-searches
```json
Request:
{
  "name": "Selaković + napad framing + 30 dana",
  "query_params": {
    "q": "Selaković",
    "framing_type_id": 3,
    "date_from": "2026-05-18"
  }
}
```

### GET /api/v1/saved-searches
### DELETE /api/v1/saved-searches/{id}

---

## 15. Admin

### GET /api/v1/admin/users
**Auth:** admin

### POST /api/v1/admin/users
```json
Request:
{
  "email": "milica@sharefoundation.info",
  "name": "Milica Jovanovic",
  "role": "researcher",
  "password": "..."
}
```

### PUT /api/v1/admin/users/{id}
### DELETE /api/v1/admin/users/{id}

### GET /api/v1/admin/sources
Vraca sve izvore sa tehnickim detaljima i statusom scraper-a.

### PUT /api/v1/admin/sources/{source_id}
**Opis:** Azuriranje konfiguracije izvora.

### GET /api/v1/admin/scraper/runs
**Query params:** `source_id`, `status`, `date_from`, `date_to`

```json
Response 200:
{
  "items": [
    {
      "id": 445,
      "source_id": "tanjug",
      "started_at": "...",
      "finished_at": "...",
      "status": "success",
      "articles_found": 8,
      "articles_new": 6,
      "articles_updated": 1,
      "duration_ms": 2340
    }
  ]
}
```

### POST /api/v1/admin/scraper/run/{source_id}
**Opis:** Rucno pokretanje jednog scraper-a.

### POST /api/v1/admin/scraper/run-all
**Opis:** Rucno pokretanje svih scraper-a (admin only).

### GET /api/v1/admin/calibration/feedback
**Opis:** Pregled svih feedbacka istrazivaca za kalibraciju.
**Query params:** `analysis_type`, `is_correct`, `applied_to_pipeline`

### POST /api/v1/admin/calibration/apply
**Opis:** Primena akumuliranih feedbacka na kalibracioni prompt.
```json
Request:
{
  "analysis_type": "political_score",
  "feedback_ids": [12, 13, 14, 15]
}
```

### POST /api/v1/admin/reanalyze
**Opis:** Pokretanje re-analize za period ili izvor.
```json
Request:
{
  "source_id": "rts",   // ili null za sve
  "date_from": "2026-06-01",
  "date_to": "2026-06-18",
  "analysis_types": ["topic", "political_score"]
}
```

### GET /api/v1/admin/pipeline/status
**Opis:** Status AI pipeline-a - koliko clanaka ceka analizu, prosecno vreme, greske.

---

## 16. Alertovi (globalni)

### GET /api/v1/alerts
**Auth:** viewer+
**Query params:** `alert_type`, `severity`, `is_read`, `date_from`, `date_to`

```json
Response 200:
{
  "unread_count": 4,
  "items": [
    {
      "id": 99,
      "alert_type": "narrative_coord",
      "severity": "high",
      "title": "Koordinacija detektovana",
      "description": "Informer, Kurir, Pink - narativna koordinacija 94% u prozoru 18-21h",
      "score": 0.94,
      "source_ids": ["informer", "kurir", "pink"],
      "date": "2026-06-18",
      "is_read": false,
      "created_at": "..."
    }
  ]
}
```

### PUT /api/v1/alerts/{id}/read
**Auth:** viewer+

### PUT /api/v1/alerts/read-all
**Auth:** viewer+

---

## 17. Export

### POST /api/v1/export/csv
**Auth:** researcher+
**Opis:** Export bilo kog pogleda u CSV.

```json
Request:
{
  "export_type": "articles",   // articles|analysis|narratives|coordination|entities
  "filters": {
    "source_ids": ["informer", "kurir"],
    "date_from": "2026-06-01",
    "date_to": "2026-06-18",
    "topic": "EU integracije"
  },
  "fields": ["title", "source_id", "published_at", "political_score", "primary_topic"]
}

Response 200:
{
  "export_id": "exp_abc123",
  "status": "processing",
  "estimated_rows": 347
}
```

### GET /api/v1/export/{export_id}/status
### GET /api/v1/export/{export_id}/download
Vraca CSV fajl kao `Content-Disposition: attachment`.

---

## 18. Webhooks i background taskovi

### Background taskovi (Celery)
- `scraper.run_source` - pokretanje jednog scraper-a
- `scraper.run_all` - pokretanje svih scraper-a
- `analysis.analyze_article` - AI analiza jednog clanka
- `analysis.batch_analyze` - batch analiza novih clanaka
- `analysis.reanalyze` - re-analiza sa novom kalibracijom
- `coordination.detect_copypaste` - detekcija copy-paste parova (daily)
- `coordination.detect_framing` - detekcija framing koordinacije (daily)
- `coordination.detect_narrative` - detekcija narativne koordinacije (daily)
- `anomalies.detect` - detekcija anomalija (daily)
- `summaries.generate_daily` - generisanje jutarnjeg rezimea (06:00 svaki dan)
- `narratives.calculate_intensity` - izracun dnevnog intenziteta narativa (midnight)

---

## 19. Error codes

```
AUTH_REQUIRED          401 - JWT token nedostaje ili istekao
INVALID_CREDENTIALS    401 - Pogresni kredencijali
FORBIDDEN              403 - Nedovoljne permisije za ovu akciju
NOT_FOUND              404 - Resurs ne postoji
VALIDATION_ERROR       422 - Neispravni parametri zahteva
RATE_LIMITED           429 - Previse zahteva
SCRAPER_ALREADY_RUNNING 409 - Scraper vec radi za ovaj izvor
ANALYSIS_IN_PROGRESS   409 - Re-analiza vec u toku
EXPORT_TOO_LARGE       400 - Previse redova za export (>50000)
SOURCE_NOT_ACTIVE      400 - Izvor nije aktivan (stub)
```

---

## 20. Napomene za implementaciju

### Intra-day upozorenje
Svi endpointi koji vracaju intra-day podatke moraju ukljuciti:
```json
"intraday_note": {
  "excluded_sources": ["rts", "tanjug"],
  "reason": "RTS i Tanjug nemaju tacno vreme objave - samo datum"
}
```

### Koordinacija - metodoloski disclaimer
Svi coordination endpointi moraju ukljuciti:
```json
"methodology_note": "Koordinacija ne dokazuje nameru. Interpretacija ostaje na istrazivacu."
```

### Konfiguracija
```python
# .env
DATABASE_URL=postgresql+asyncpg://user:pass@localhost/mediascope
REDIS_URL=redis://localhost:6379
SECRET_KEY=...
ANTHROPIC_API_KEY=...
JWT_ALGORITHM=HS256
JWT_EXPIRE_HOURS=24
MAX_PER_PAGE=100
EXPORT_MAX_ROWS=50000
INTRADAY_EXCLUDED_SOURCES=rts,tanjug
```

### Struktura projekta
```
backend/
  api/
    v1/
      auth.py
      dashboard.py
      articles.py
      sources.py
      topics.py
      framing.py
      narratives.py
      coordination.py
      anomalies.py
      origin.py
      political.py
      search.py
      watchlists.py
      admin.py
      alerts.py
      export.py
    deps.py          # get_db, get_current_user, require_role
    router.py        # agregacija svih rutera
  models/            # SQLAlchemy modeli
  schemas/           # Pydantic v2 sheme
  services/          # business logika
    scraper_service.py
    analysis_service.py
    coordination_service.py
    export_service.py
  tasks/             # Celery taskovi
  db.py              # engine, session
  config.py          # Settings
  main.py            # FastAPI app, middleware, CORS
```
