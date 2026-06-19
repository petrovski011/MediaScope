# MediaScope Scraper — Session Log
> Zadnja sesija: 2026-06-18/19 | Status: produkcijski spreman za testiranje

---

## Trenutno stanje sistema

- **Baza**: `/Users/andrejpetrovski/Downloads/MediaScope/data/mediascope.db` (SQLite, WAL mode)
- **Ukupno članaka**: ~2.977
- **Aktivnih izvora**: 19 (juzne.py = UnsupportedScraper stub)
- **Pokretanje scrapera**: `cd backend && python3 scrapers/runner.py --all`
- **Scheduler**: `cd backend && python3 -m scrapers.scheduler` (blokira terminal; za server/Docker)

---

## Arhitektura scrapera

```
backend/
  scrapers/
    base.py          — BaseScraper, ArticleData dataclass, ScraperError
    utils.py         — clean_text, cyrillic_to_latin, parse_sr_date, extract_schema_org, unique_urls
    scheduler.py     — APScheduler, hourly cron, staggered 3-min gaps (n1@:00 ... politika@:57)
    runner.py        — CLI: --all / --source X / --test X / --test-all / --stats
    sources/
      __init__.py    — SCRAPERS dict + STAGGERED_ORDER list
      *.py           — jedan fajl po izvoru
  db.py              — save_article(), init_db(), get_stats(), get_recent()
data/
  mediascope.db
docs/
  (ovaj fajl)
```

### Tipovi scrapera po metodi prikupljanja URL-ova

| Metod | Izvori |
|-------|--------|
| Global RSS `/feed/` | n1, danas, insajder, nova, radar, birn, vreme |
| Single RSS (non-WP) | kurir (`/rss`), sd (`/rss.xml`) |
| Multi-feed RSS | blic (10 feedova), b92 (9 feedova), prva (2 RSS + 3 HTML) |
| RSS + HTML fallback | telegraf |
| HTML homepage (svi linkovi) | informer, mondo, pink, tanjug, politika, rts |

---

## Popravke urađene u ovoj sesiji

### 1. Scrapers — tekst (HTML fetch za puni sadržaj)
- **nova.py** — `resp.text` → `resp.content`; Tailwind class filter ubijao sadržaj; sada direktno `div.rich-text-block`
- **n1.py** — `resp.text` → `resp.content`; HTML fetch za puni tekst umjesto RSS excerpta
- **sd.py** — dodato HTML fetch za puni tekst (RSS davao ~35w, HTML ~300w)
- **insajder.py** — isti pattern kao n1/sd
- **danas.py** — isti pattern
- **b92.py** — `section.single-news` umjesto `main` (eliminisao 960w sidebarskog šuma)
- **prva.py** — `div.single-news-main` umjesto `main`
- **rts.py** — dual-format: `div.short-story-body` (preskače prazni placeholder) + `div.story-wrapper` fallback

### 2. Scrapers — tagovi i autori
- **tanjug.py** — `tag_el.get_text()` spajao tagove bez razmaka → `find_all("a")` iteracija
- **politika.py** — `time.sleep(1.0)` (429 rate limit); tagovi `cyrillic_to_latin()`
- **pink.py** — `div.news-single-content`; `a.get_text().lstrip("#")` (skida hashtag prefix)
- **informer.py** — `_parse_informer_author`: split na `Novinar\d`; strip `Izvor:`/`Autor:` prefix
- **blic.py** — `_parse_blic_author`: split na lowercase→uppercase granicu (ime+bio spajani)

### 3. Scrapers — pokrivanje kategorija
- **blic.py** — dodati feedovi: `Svet`, `Zabava/Kultura`, `Zabava/Zdravlje` (bili propušteni, 3×70 art/run)
- **b92.py** — dodati feedovi: `sport`, `sport/fudbal`, `sport/kosarka` (30 art/run propuštano)
- **kurir.py** — category iz URL-a (schema.org articleSection uvijek prazan); `kurir.rs/KATEGORIJA/...`
- **nova.py** — category iz URL-a + schema.org (bio hardcoded `None`)

### 4. db.py — ključne popravke
- `save_article()` sada selektuje i `text` kolonu (ne samo `content_hash`)
- Ako `existing text < 200 chars` → uvijek full UPDATE (stari prazni članci se osvježavaju)
- Ako `same_hash AND good text` → metadata-only UPDATE (tags/author/category se uvijek propagiraju)
- content_hash = `hash(title + text)` — **ne uključuje tags/author/category**

### 5. scheduler.py — kritičan bug fix
- Bio komentarisan: `# TODO: persist article to database` — **nikad nije čuvao u DB**
- Dodat `import db` + `db.init_db()` pri startu + `db.save_article(article)` u `_run_scraper()`

---

## Migracije baze (jednom urađene)

```sql
-- Politika: Cyrillic → Latin tagovi (28 članaka)
-- Informer: "Novinar18" pattern + "Izvor:" prefix (30 članaka)
-- Tanjug: joined tagovi re-fetched sa live stranice (11 članaka)
-- Blic: author bio strip (177 članaka)
```
Sve migracije su primijenjene direktno na DB fajlu.

---

## Kvalitet podataka — trenutni status

| Metrika | Vrijednost |
|---------|-----------|
| Ukupno članaka | 2.977 |
| Sa tekstom (>5 chars) | ~98.5% |
| Sa timestampom | ~97.4% |
| Sa naslovom | 100% |
| Sa slikom | ~94% |
| Dupli URL-ovi | 0 |

### Per-source prosječan broj riječi (nakon popravki)
```
informer  1824w | tanjug  1232w | b92    913w | politika 460w
rts        400w | insajder 368w | prva  334w  | sd       300w
n1         285w | danas   275w  | pink  251w  | nova     248w
```

### Preostali edge caseovi (prihvatljivi)
- **Nova**: 18 praznih (stari video/galerija članci)
- **Pink**: 22 praznih (isto)
- **RTS**: 6 praznih (video format)
- **N1/SD/Danas**: ~30-38 kratkih (<30w) — genuinely short breaking news ili paywalled
- **Tanjug/RTS/Radar timestamps**: `2026-06-18T00:00:00` — sajt ne izlaže tačno vrijeme

---

## Bitne tehničke napomene

### feedparser — uvijek bytes, nikad text
```python
feed = feedparser.parse(resp.content)   # ✅
feed = feedparser.parse(resp.text)      # ❌ encoding bugovi
```

### BS4 class lambda — c je jedan class string
```python
# c je svaki pojedinačni class name, NE cijela class lista
soup.find(class_=lambda c: c and "ad" in c)
# "ad" in "shadow-lg" = False ✅
# "ad" in "fade-visible" = False ✅
# ali "ad" in "advertisement" = True ✅
```

### cyrillic_to_latin()
```python
from scrapers.utils import cyrillic_to_latin
# Koristi se u: rts.py, politika.py
# Potrebno za sve izvore koji imaju Ćirilično/Latinično miješanje
```

### content_hash ne pokriva metadata
```python
# hash(title + text) — tags/author/category NISU u hash-u
# Promjena taga ne triggeruje update ako se tekst nije promjenio
# db.py je popravljen da uvijek update-uje metadata
```

---

## Kako pokrenuti

```bash
# Jednokratni scrape svih izvora (upisuje u DB)
cd /Users/andrejpetrovski/Downloads/MediaScope/backend
python3 scrapers/runner.py --all

# Test jednog scrapera (bez upisa u DB)
python3 scrapers/runner.py --test blic

# Statistike
python3 scrapers/runner.py --stats

# Scheduler (blokira, za server)
python3 -m scrapers.scheduler
python3 -m scrapers.scheduler --list   # prikaži raspored
```

---

## Sljedeći koraci (nisu urađeni)

- [ ] Deployment na server (vidjeti `/memory/project_deployment.md`)
- [ ] Docker compose — scheduler kao service
- [ ] API endpoint za dohvat članaka (vidjeti `docs/MediaScope_API_Spec_v1.md`)
- [ ] AI pipeline integracija (vidjeti `docs/MediaScope_AI_Pipeline_v1.md`)
- [ ] Telegraf category noise (neke kategorije sadrže naslove članaka — manji problem)
- [ ] B92 sport potencijalno nepotpuno — `/rss/sport` ima samo 20 unosa, može biti više podkategorija
