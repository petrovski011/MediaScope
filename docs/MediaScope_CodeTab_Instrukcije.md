# MediaScope - Instrukcije za implementaciju (Claude Code Tab)

## Kontekst projekta

MediaScope je platforma za pracenje srpskih medija i analizu narativa, koju razvija SHARE Fondacija.
Projekat se nalazi na: `/Users/andrejpetrovski/Downloads/MediaScope/`

Skrejper infrastruktura je vec implementirana i radi:
- 19/20 scraper-a su aktivni, 1 stub (Juzne vesti - Cloudflare blokada)
- SQLite baza sa ~3.000 clanaka na lokaciji `data/mediascope.db`
- Scraper kod u `backend/scrapers/`

Sledeci korak je implementacija backend API-ja, PostgreSQL baze, i AI pipeline-a.

---

## Dokumenti koje treba procitati pre pocetka

Procitaj SVE sledece dokumente redosledom kojim su navedeni - svaki zavisi od prethodnog:

1. **`docs/MediaScope_Metodologija_v2.docx`** - Metodologija istrazivanja
   - Sta platforma treba da meri i kako
   - Koje analize su podrzane podacima, koje imaju ogranicenja
   - Posebno vazno: RTS i Tanjug nemaju tacno vreme (samo datum) - ovo se mora respektovati svuda

2. **`docs/MediaScope_DataModel_v1.sql`** - PostgreSQL data model
   - Kompletna shema baze sa svim tabelama, indexima, trigerima i seed podacima
   - Pokretanje: `psql mediascope < docs/MediaScope_DataModel_v1.sql`

3. **`docs/MediaScope_API_Spec_v1.md`** - FastAPI specifikacija
   - Svi endpointi sa request/response formatima
   - Role-based access (admin/researcher/viewer)
   - Konvencije za paginaciju, greske, datume

4. **`docs/MediaScope_AI_Pipeline_v1.md`** - AI pipeline specifikacija
   - Redosled analiticnih koraka (NER -> tema -> framing -> politicko -> narativ)
   - Konkretni promptovi za svaki korak
   - Cost kalkulacija i batch logika
   - Faze implementacije (MVP prvo, pa prosirivanje)

5. **`docs/MediaScope_Scraper_Specifikacija.md`** - Scraper specifikacija
   - Specificnosti po sajtu (RTS/Tanjug bez vremena, Pink bez autora itd.)
   - Vec implementirano - korisno za razumevanje podataka

---

## Sta je vec implementirano

```
backend/
  scrapers/
    base.py         - BaseScraper, ArticleData dataclass
    utils.py        - cyrillic_to_latin, parse_sr_date, clean_text, extract_schema_org
    sources/        - 20 scraper-a (19 aktivnih + 1 stub)
    scheduler.py    - APScheduler, hourly, staggered
    runner.py       - CLI: --test, --all, --source, --stats
  db.py             - SQLite storage (privremeno, zamenjuje se PostgreSQL)
  requirements.txt
data/
  mediascope.db     - SQLite baza, ~3.000 clanaka
```

---

## Sta treba implementirati

### Faza 1: Infrastruktura (pocni ovde)

**1.1 PostgreSQL setup**
- Kreiraj `docker-compose.yml` sa PostgreSQL 16 i Redis
- Pokreni data model: `psql mediascope < docs/MediaScope_DataModel_v1.sql`
- Migriraj podatke iz SQLite u PostgreSQL (skripta za migraciju)
- Alembic konfiguracija za buduce migracije

**1.2 FastAPI skeleton**
Struktura:
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
    deps.py          - get_db(), get_current_user(), require_role()
    router.py        - agregacija svih rutera
  models/            - SQLAlchemy 2.0 async modeli (po tabelama iz data modela)
  schemas/           - Pydantic v2 sheme (request/response po API specifikaciji)
  services/          - business logika odvojena od ruta
    scraper_service.py
    analysis_service.py
    coordination_service.py
    export_service.py
  tasks/             - Celery taskovi
  db.py              - async engine, session factory
  config.py          - Settings (pydantic-settings, .env)
  main.py            - FastAPI app, middleware, CORS
```

**1.3 Autentikacija**
- JWT sa python-jose
- Bcrypt za lozinke
- Role-based access: admin > researcher > viewer
- Implementirati: POST /auth/login, POST /auth/refresh, GET /auth/me

### Faza 2: Core API endpointi

Implementiraj redosledom prioriteta:

1. `GET /api/v1/articles` + `GET /api/v1/articles/{id}` - osnova svega
2. `GET /api/v1/sources` + `GET /api/v1/sources/{source_id}` - profili medija
3. `GET /api/v1/dashboard/summary` - jutarnji pregled
4. `GET /api/v1/search` - pretraga sa filterima
5. `POST /api/v1/articles/{id}/feedback` - RLHF kalibracija
6. Watchliste i sacuvane pretrage
7. Alertovi
8. Export (asinhroni, CSV)
9. Admin endpointi

Za svaki endpoint:
- Implementiraj Pydantic sheme tacno po API specifikaciji
- Dodaj role checking kroz `require_role()` dependency
- Paginacija: `?page=1&per_page=20`
- Filtri po source_ids, date_from, date_to na svim relevantnim endpointima

### Faza 3: AI Pipeline - MVP

Implementiraj redosledom iz pipeline specifikacije:

**3.1 Korak 1+2+4: NER + Tema + Politicko pozicioniranje**
- Celery task: `analysis.analyze_article`
- Batch API pozivi (Anthropic)
- Rezultati u `article_analysis` i `article_entities` tabelama
- Promptovi su u pipeline specifikaciji - koristiti ih doslovno

**3.2 Copy-paste detekcija**
- pgvector cosine similarity (BEZ AI - jeftinije i preciznije)
- Celery task: `coordination.detect_copypaste`
- Threshold: 0.85, alert za parove > 0.92
- Rezultati u `coordination_copypaste` tabeli

**3.3 Jutarnji rezime**
- Celery task: `summaries.generate_daily`
- Pokrece se u 05:00 svaki dan
- Prompt je u pipeline specifikaciji

**3.4 Embedding generisanje**
- Voyage API (voyage-3-lite) ili OpenAI text-embedding-3-small
- Input: `title + " " + text[:1000]`
- Dimenzija 512, HNSW index u pgvector

### Faza 4: Prosirivanje pipeline-a

Po redosledu iz pipeline specifikacije Faze 2 i 3.

---

## Specificnosti koje moraju biti implementirane

### RTS i Tanjug - bez tacnog vremena
```python
# Ovo se mora potovati SVUDA gde se koristi timestamp:

INTRADAY_EXCLUDED_SOURCES = ["rts", "tanjug"]

# Svaki endpoint koji vraca intraday podatke mora ukljuciti:
"intraday_note": {
    "excluded_sources": ["rts", "tanjug"],
    "reason": "RTS i Tanjug nemaju tacno vreme objave - samo datum"
}
```

### Koordinacija - metodoloski disclaimer
```python
# Svaki coordination endpoint mora ukljuciti:
"methodology_note": "Koordinacija ne dokazuje nameru. Interpretacija ostaje na istrazivacu."
```

### Politicka analiza - neutralnost
AI model mora biti konfigurisan da bude empirijski neutralan - ne procenjuje "ispravnost"
politickih stavova, vec objektivno meri kako clanak pozicionira vladajucu strukturu.

---

## Environment i zavisnosti

### .env fajl (kreiraj)
```
DATABASE_URL=postgresql+asyncpg://mediascope:password@localhost:5432/mediascope
REDIS_URL=redis://localhost:6379
SECRET_KEY=<generisi_random_64_char_string>
ANTHROPIC_API_KEY=<anthropic_api_key>
JWT_ALGORITHM=HS256
JWT_EXPIRE_HOURS=24
MAX_PER_PAGE=100
EXPORT_MAX_ROWS=50000
INTRADAY_EXCLUDED_SOURCES=rts,tanjug
ANTHROPIC_MODEL=claude-haiku-4-5
COPYPASTE_THRESHOLD=0.85
```

### requirements.txt (dodati uz postojece)
```
fastapi>=0.111.0
uvicorn[standard]>=0.29.0
sqlalchemy[asyncio]>=2.0.0
asyncpg>=0.29.0
alembic>=1.13.0
pydantic>=2.0.0
pydantic-settings>=2.0.0
python-jose[cryptography]>=3.3.0
passlib[bcrypt]>=1.7.4
python-multipart>=0.0.9
redis[hiredis]>=5.0.0
celery[redis]>=5.3.0
anthropic>=0.25.0
pgvector>=0.2.0
```

### docker-compose.yml (kreiraj)
```yaml
version: '3.8'
services:
  postgres:
    image: pgvector/pgvector:pg16
    environment:
      POSTGRES_DB: mediascope
      POSTGRES_USER: mediascope
      POSTGRES_PASSWORD: password
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"

volumes:
  postgres_data:
```

---

## Testiranje

Za svaki implementirani deo:
1. Pokretanje: `uvicorn backend.main:app --reload`
2. Swagger docs: `http://localhost:8000/docs`
3. Test auth: `POST /api/v1/auth/login` sa admin kredencijalima
4. Test articles: `GET /api/v1/articles?per_page=5`

Za AI pipeline test:
```bash
python3 -m backend.tasks.analysis --test --article-id 1
```

---

## Napomene za implementaciju

- Koristi async/await svuda (SQLAlchemy 2.0 async, asyncpg)
- Svaki servis u `services/` treba da bude nezavisan od FastAPI (testabilnost)
- Logovanje kroz Python `logging` modul, ne print
- Sve greske kroz FastAPI HTTPException sa error kodovima iz API specifikacije
- CORS: dozvoliti `http://localhost:3000` za razvoj (React frontend dolazi kasnije)
- Uvek ukljuci `has_timestamp_time` flag iz `sources` tabele kada radis sa timestamps
- `article_analysis` tabela je 1:1 sa `articles` - jedan clanak, jedna analiza

---

## Redosled rada

1. Procitaj sve dokumente iz `docs/` foldera
2. Pokreni `docker-compose up -d`
3. Inicijalizuj PostgreSQL shemu
4. Implementiraj migraciju SQLite -> PostgreSQL
5. FastAPI skeleton + auth
6. Core article/source endpointi
7. Dashboard endpoint
8. AI pipeline MVP (NER + tema + politicko)
9. Copy-paste detekcija
10. Jutarnji rezime
11. Ostali endpointi po prioritetu iz API specifikacije
