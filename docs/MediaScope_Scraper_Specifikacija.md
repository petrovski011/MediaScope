# MediaScope - Scraper Specifikacija
**Verzija:** 1.0  
**Datum:** Jun 2026  
**Status:** Radna verzija

---

## 1. Arhitektura scraping sistema

### 1.1 Frekvencija i raspored

Scraper radi **svaki sat**, ne jednom dnevno. Razlog: intra-day analiza je jedna od kljucnih analitickih vrednosti platforme i zahteva timestamp objave koji se moze pouzdano koristiti samo ako smo sami scrapeovali u tom vremenskom prozoru.

Raspored po principu **staggering** - svaki scraper krece u drugom minutu kako bi se izbeglo simultano opterecenje VPS-a i bot detekcija:

```
:00 - N1
:03 - Blic
:06 - Telegraf
:09 - Kurir
:12 - Srbija danas
:15 - RTS
:18 - Nova
:21 - Informer
:24 - Danas
:27 - B92
:30 - Mondo
:33 - Pink
:36 - BIRN
:39 - Radar
:42 - Prva TV
:45 - Juzne vesti
:48 - Vreme
:51 - Insajder
:54 - Tanjug
:57 - Politika
```

Ukupno trajanje jednog ciklusa: 57 minuta, sto se komforno uklapa u sat.

### 1.2 Deduplication

Svaki clanak dobija jedinstveni **content hash** (SHA-256 nad kombinacijom URL + naslov + tekst). Pre insertovanja u bazu proveravamo:

1. Da li URL vec postoji u bazi
2. Ako postoji - da li se hash razlikuje od prethodne verzije

Ako se hash razlikuje - clanak je izmenjen. Cuvamo **novu verziju** sa timestampom izmene, a originalnu verziju zadrzavamo. Baza cuva kompletnu istoriju svih verzija svakog clanka.

### 1.3 Detekcija izmena clanaka

```python
def process_article(url, title, text, published_at):
    content_hash = sha256(f"{url}{title}{text}".encode()).hexdigest()
    
    existing = db.query(Article).filter_by(url=url).first()
    
    if not existing:
        # Novi clanak
        db.add(Article(url=url, title=title, text=text, 
                      content_hash=content_hash,
                      published_at=published_at,
                      version=1))
    elif existing.content_hash != content_hash:
        # Izmenjen clanak - sacuvaj novu verziju
        db.add(ArticleVersion(
            article_id=existing.id,
            title=title, text=text,
            content_hash=content_hash,
            updated_at=datetime.now(),
            version=existing.version + 1
        ))
        existing.content_hash = content_hash
        existing.version += 1
```

### 1.4 Live blogovi

Live blogovi su poseban format koji se kontinualno azurira. Detekcija:
- URL sadrzi `/live/` ili `/uzivo/` ili `/blog/`
- Ili je clanak oznacen schema.org tipom `LiveBlogPosting`

Za live blogove: scraper prati isti URL na svakom ciklusu i cuva **svaki novi unos** kao poseban zapis u tabeli `live_blog_entries`, ne kao novi clanak.

### 1.5 Error handling

Svaki scraper ima sledece slojeve zastite:

```
Timeout: 30 sekundi po requestu
Retry: 3 pokusaja sa exponential backoff (5s, 15s, 45s)
Circuit breaker: posle 5 uzastopnih failova, scraper se pauzira 1h
Alert: posle 3 uzastopna sata failova, admin dobija alert u platformi
```

Tipovi gresaka koji se loguju:
- `HTTP_ERROR` - sajt vratio 4xx/5xx
- `TIMEOUT` - sajt nije odgovorio
- `PARSE_ERROR` - HTML struktura se promenila, selektori vise ne rade
- `EMPTY_CONTENT` - clanak pronadjen ali tekst je prazan
- `BLOCKED` - bot detekcija aktivirana (429 ili Cloudflare challenge)

`PARSE_ERROR` je posebno vazan - znaci da je sajt promenio HTML strukturu i scraper treba rucno da se azurira. Ovo se alertuje odmah, ne posle 3h.

---

## 2. Tehnicke kategorije sajtova

Pre detaljnog pregleda, sajtove delimo u tehnicke kategorije:

| Kategorija | Opis | Pristup |
|---|---|---|
| **RSS-first** | Imaju RSS feed koji je dovoljan za listing | Citamo RSS, fetchujemo pojedinacne clanke |
| **WordPress** | Koriste WordPress - imaju RSS + REST API | RSS ili `/wp-json/wp/v2/posts` |
| **Custom listing** | Imaju listing stranicu sa paginacijom | Scrapeujemo listing, pa clanke |
| **JS-rendered** | Sadrzaj se renderuje u browseru | Zahteva Playwright, ne BeautifulSoup |

---

## 3. Profil svakog sajta

---

### 3.1 N1 (n1info.rs)

| Atribut | Vrednost |
|---|---|
| **URL** | https://n1info.rs |
| **Listing** | https://n1info.rs/vesti/ (paginacija: /vesti/2/, /vesti/3/...) |
| **RSS** | https://n1info.rs/feed/ |
| **Kategorija** | RSS-first + custom listing |
| **Rendering** | Server-side (BeautifulSoup dovoljan) |
| **Timestamp format** | `og:published_time` u meta tagovima (ISO 8601 sa timezone) |
| **Izmene** | `og:updated_time` u meta tagovima |
| **Paywall** | Ne |
| **Bot detekcija** | Nije primecena |
| **Live blog** | Da, postoji format |

**Strategija:** RSS za listing novih clanaka, fetch pojedinacnih clanaka za pun tekst i meta podatke. `og:published_time` i `og:updated_time` su pouzdani.

**Kljucni meta tagovi:**
```html
<meta property="og:published_time" content="2026-06-17T07:27:37.834939+02:00">
<meta property="og:updated_time" content="2026-06-17T07:27:37.834939+02:00">
```

**Napomena:** N1 ima i engleski sadrzaj na `/english/` - ignorisemo, scrapujemo samo srpski.

---

### 3.2 Blic (blic.rs)

| Atribut | Vrednost |
|---|---|
| **URL** | https://www.blic.rs |
| **Listing** | https://www.blic.rs/najnovije |
| **RSS** | https://www.blic.rs/rss (potrebna verifikacija) |
| **Kategorija** | Custom listing, verovatno RSS |
| **Rendering** | Potrebna verifikacija (moze biti JS) |
| **Vlasnik** | Ringier (Swiss Media Group) |
| **Paywall** | Delom - premium sadrzaj iza paywalla |

**Strategija:** Verifikovati RSS feed. Blic ima Ringier infrastrukturu koja je standardizovana - verovatno ima pouzdane meta tagove za timestamp. Paywall clanke skipujemo ili biljezimo kao `paywall: true`.

**POTREBNO PROVERITI RUCNO:**
- Da li RSS feed postoji i da li je kompletan
- Da li listing stranica zahteva JS rendering
- Struktura HTML clanka (naslov, tekst, autor, datum selektor)

---

### 3.3 Telegraf (telegraf.rs)

| Atribut | Vrednost |
|---|---|
| **URL** | https://www.telegraf.rs |
| **Listing** | https://www.telegraf.rs/ (naslovna ima najnovije) |
| **RSS** | Postoji, URL na https://www.telegraf.rs/teme/rss (tema page, ne direktan feed - proveriti /feed/) |
| **Kategorija** | Custom CMS |
| **Rendering** | Potrebna verifikacija |
| **Paywall** | Ne |

**POTREBNO PROVERITI RUCNO:**
- Direktna RSS URL (verovatno /feed/ ili /rss/)
- Da li sadrzi `published_time` i `updated_time` u meta tagovima
- HTML struktura clanka

---

### 3.4 Kurir (kurir.rs)

| Atribut | Vrednost |
|---|---|
| **URL** | https://www.kurir.rs |
| **Listing** | https://www.kurir.rs/najnovije-vesti |
| **RSS** | Postoji (https://www.kurir.rs/rss-feed stranica postoji, proveriti /feed/ ili /rss/) |
| **Kategorija** | Custom CMS |
| **Rendering** | Potrebna verifikacija - koristi static.kurir.rs za slike, moze biti JS |
| **Napomena** | Ima vise sub-portala: biznis.kurir.rs, zdravlje.kurir.rs, stil.kurir.rs - scrapujemo samo glavni |

**POTREBNO PROVERITI RUCNO:**
- Tacan RSS URL
- Da li je listing JS-rendered
- HTML struktura clanka i timestamp meta tagovi

---

### 3.5 Srbija danas (sd.rs)

| Atribut | Vrednost |
|---|---|
| **URL** | https://www.sd.rs |
| **Listing** | Potrebna verifikacija |
| **RSS** | Potrebna verifikacija |
| **Kategorija** | Nepoznato |
| **Rendering** | Potrebna verifikacija |

**POTREBNO PROVERITI RUCNO:** Kompletan tehnicki profil.

---

### 3.6 RTS (rts.rs)

| Atribut | Vrednost |
|---|---|
| **URL** | https://www.rts.rs |
| **Listing** | https://www.rts.rs/page/stories/sr/ ili rubrike |
| **RSS** | Da - https://www.rts.rs/rss/sr.html (vise feedova po rubrici) |
| **Kategorija** | RSS-first |
| **Rendering** | Server-side |
| **Paywall** | Ne |
| **Napomena** | Koristi cirilicu - potrebna normalizacija na latinicu |

**Strategija:** RTS ima strukturisane RSS feedove po rubrici (politika, region, svet, srbija danas, hronika, drustvo, ekonomija). Koristimo sve relevantne. Sadrzaj je na cirilici - normalizujemo na latinicu pri unosu u bazu.

---

### 3.7 Nova (nova.rs)

| Atribut | Vrednost |
|---|---|
| **URL** | https://nova.rs |
| **Listing** | Potrebna verifikacija |
| **RSS** | Potrebna verifikacija |
| **Kategorija** | United Media infrastruktura (slicno N1) |
| **Rendering** | Verovatno server-side |
| **Napomena** | Deo United Media grupe kao i N1, B92, Danas, Radar - moguca slicna infrastruktura |

**Strategija:** Proveriti da li koristi istu platformu kao N1. Ako da, isti scraper moze biti adaptiran.

---

### 3.8 Informer (informer.rs)

| Atribut | Vrednost |
|---|---|
| **URL** | https://informer.rs |
| **Listing** | https://informer.rs/najnovije ili naslovna |
| **RSS** | Da - https://informer.rs/rss |
| **Kategorija** | RSS-first |
| **Rendering** | Server-side |
| **Paywall** | Ne |

**Strategija:** RSS feed je dostupan i aktivan. Koristimo RSS za listing, fetchujemo clanke za pun tekst.

---

### 3.9 Danas (danas.rs)

| Atribut | Vrednost |
|---|---|
| **URL** | https://www.danas.rs |
| **Listing** | https://www.danas.rs/najnovije-vesti/ |
| **RSS** | Da - https://www.danas.rs/feed/ (WordPress standard) |
| **REST API** | Da - https://www.danas.rs/wp-json/wp/v2/posts |
| **Kategorija** | **WordPress** |
| **Rendering** | Server-side |
| **Paywall** | Delom (Klub citalaca) |
| **Napomena** | `meta-generator: WordPress 7.0` potvrdjeno |

**Strategija:** WordPress REST API je najpouzdaniji pristup - vraca strukturisani JSON sa svim meta podacima ukljucujuci timestamp. Alternativno RSS feed. Paywall clanke biljezimo kao `paywall: true` i skipujemo analizu teksta.

**REST API primer:**
```
GET https://www.danas.rs/wp-json/wp/v2/posts?per_page=20&orderby=date
```

---

### 3.10 B92 (b92.net)

| Atribut | Vrednost |
|---|---|
| **URL** | https://www.b92.net |
| **Listing** | Potrebna verifikacija |
| **RSS** | Potrebna verifikacija |
| **Kategorija** | United Media infrastruktura |
| **Rendering** | Potrebna verifikacija |

**Napomena:** B92 je deo United Media grupe. Proveriti da li deli infrastrukturu sa N1/Nova/Danas/Radar.

---

### 3.11 Mondo (mondo.rs)

| Atribut | Vrednost |
|---|---|
| **URL** | https://mondo.rs |
| **Listing** | Potrebna verifikacija |
| **RSS** | Potrebna verifikacija |
| **Kategorija** | Telekom Srbija infrastruktura |
| **Rendering** | Potrebna verifikacija |

**POTREBNO PROVERITI RUCNO:** Kompletan tehnicki profil.

---

### 3.12 Pink (pink.rs)

| Atribut | Vrednost |
|---|---|
| **URL** | https://pink.rs |
| **Listing** | Potrebna verifikacija |
| **RSS** | Potrebna verifikacija |
| **Kategorija** | Nepoznato |
| **Rendering** | Moze biti JS-heavy (TV portal) |

**Napomena:** TV portali cesto imaju vise video sadrzaja i mogu biti JS-rendered. POTREBNO PROVERITI.

---

### 3.13 BIRN Srbija (birn.rs)

| Atribut | Vrednost |
|---|---|
| **URL** | https://birn.rs |
| **Listing** | Potrebna verifikacija |
| **RSS** | Verovatno da (NGO portali cesto imaju RSS) |
| **Kategorija** | Verovatno WordPress |
| **Rendering** | Server-side |
| **Napomena** | Ima i engleski sadrzaj - scrapujemo samo srpski |

**POTREBNO PROVERITI RUCNO:** Tehnicki profil i da li je WordPress.

---

### 3.14 Radar (radar.rs)

| Atribut | Vrednost |
|---|---|
| **URL** | https://radar.rs |
| **Listing** | Potrebna verifikacija |
| **RSS** | Potrebna verifikacija |
| **Kategorija** | United Media infrastruktura |
| **Rendering** | Potrebna verifikacija |

**Napomena:** Deo United Media grupe. Verovatno slicna infrastruktura kao N1.

---

### 3.15 Prva TV (prva.rs)

| Atribut | Vrednost |
|---|---|
| **URL** | https://www.prva.rs |
| **Listing** | Potrebna verifikacija |
| **RSS** | Potrebna verifikacija |
| **Kategorija** | Antenna Group infrastruktura |
| **Rendering** | Moze biti JS-heavy (TV portal) |

**POTREBNO PROVERITI RUCNO:** Teknicki profil.

---

### 3.16 Juzne vesti (juznevesti.com)

| Atribut | Vrednost |
|---|---|
| **URL** | https://www.juznevesti.com |
| **Listing** | https://www.juznevesti.com/ (naslovna) |
| **RSS** | Verovatno da |
| **Kategorija** | Verovatno WordPress (regionalni portali cesto) |
| **Rendering** | Server-side |

**POTREBNO PROVERITI RUCNO:** Tehnicki profil.

---

### 3.17 Vreme (vreme.rs)

| Atribut | Vrednost |
|---|---|
| **URL** | https://www.vreme.rs |
| **Listing** | Potrebna verifikacija |
| **RSS** | Potrebna verifikacija |
| **Kategorija** | Nedeljnik - manji broj objava |
| **Napomena** | Nedeljnik, objavljuje manje tekstova - moze biti 5-10 clanaka nedeljno, ne 50+ dnevno |

**POTREBNO PROVERITI RUCNO:** Tehnicki profil i frekvencija objava.

---

### 3.18 Insajder (insajder.net)

| Atribut | Vrednost |
|---|---|
| **URL** | https://insajder.net |
| **Listing** | https://insajder.net/ (naslovna, vidljivi nedavni clanaci) |
| **RSS** | Potrebna verifikacija |
| **Kategorija** | Nepoznato |
| **Rendering** | Verovatno server-side |
| **Napomena** | Istrazivaoki medij, manji broj ali duzi tekstovi |

**POTREBNO PROVERITI RUCNO:** Tehnicki profil.

---

### 3.19 Tanjug (tanjug.rs)

| Atribut | Vrednost |
|---|---|
| **URL** | https://www.tanjug.rs |
| **Listing** | Potrebna verifikacija |
| **RSS** | Verovatno da (novinska agencija standardno ima RSS) |
| **Kategorija** | Novinska agencija - specificna infrastruktura |
| **Napomena** | Drzavna novinska agencija, objavljuje vesti koje preuzimaju drugi mediji - vazno za origin tracking |

**POSEBNA NAPOMENA:** Tanjug je novinska agencija - njeni tekstovi se pojavljuju gotovo doslovno na drugim portalima. Copy-paste detekcija izmedju Tanjuga i ostalih medija je direktno merilo koliko medij zavisi od drzavnih izvora.

---

### 3.20 Politika (politika.rs)

| Atribut | Vrednost |
|---|---|
| **URL** | https://www.politika.rs |
| **Listing** | Potrebna verifikacija |
| **RSS** | Verovatno da |
| **Kategorija** | Nepoznato (stari medij, mozda custom CMS) |
| **Napomena** | Ima i cirilicnu i latinicnu verziju - proveriti koja se preferira |

**POTREBNO PROVERITI RUCNO:** Tehnicki profil, URL struktura za latinicu vs cirilica.

---

## 4. Sumarni pregled

### Pouzdanost RSS-a

| Status | Sajtovi |
|---|---|
| **Potvrdjeno ima RSS** | N1, RTS, Informer, Danas (WordPress) |
| **Verovatno ima RSS** | Kurir, Telegraf, BIRN, Juzne vesti, Vreme, Tanjug, Politika |
| **Nepoznato** | Blic, Srbija danas, Nova, B92, Mondo, Pink, Radar, Prva TV, Insajder |

### WordPress sajtovi (privilegovani pristup)

Potvrdjeno WordPress: **Danas**  
Verovatno WordPress: **BIRN, Juzne vesti, Insajder, Vreme**

WordPress sajtovi dobijaju REST API pristup kao primarnu strategiju, RSS kao fallback.

### JS rendering rizik

Visok rizik (TV portali): **Pink, Prva TV**  
Srednji rizik: **Kurir, Srbija danas, Mondo, Radar**  
Nizak rizik: **N1, RTS, Informer, Danas, Telegraf, Juzne vesti, Vreme, Insajder, BIRN, Tanjug**

### United Media grupa (5 sajtova)

N1, Nova, Danas, B92, Radar - ako dele infrastrukturu, jedan scraper moze biti osnova za sve 5 uz minimalne adaptacije. **Proveriti** da li koriste istu platformu.

---

## 5. Prioritet implementacije

### Faza 1 - Odmah implementirati (jasna tehnika, potvrdjeni RSS)

1. **N1** - RSS + meta tagovi, potpuno jasno
2. **RTS** - RSS po rubrici, potpuno jasno
3. **Informer** - RSS potvrdjen
4. **Danas** - WordPress REST API, najpouzdaniji

### Faza 2 - Implementirati nakon rucne verifikacije

5. Telegraf
6. Kurir
7. Tanjug
8. Politika
9. BIRN
10. Juzne vesti
11. Insajder
12. Vreme

### Faza 3 - Zahteva detaljniju analizu (potencijalni JS rendering)

13. Blic
14. Nova
15. B92
16. Radar
17. Mondo
18. Srbija danas
19. Pink
20. Prva TV

---

## 6. Zajednicka scraper arhitektura

### Base scraper klasa

```python
class BaseScraper:
    def __init__(self, source_id: str, source_url: str):
        self.source_id = source_id
        self.source_url = source_url
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'MediaScope Research Bot/1.0'
        })
    
    def fetch(self, url: str) -> BeautifulSoup:
        """Fetch URL sa retry logikom"""
        for attempt in range(3):
            try:
                response = self.session.get(url, timeout=30)
                response.raise_for_status()
                return BeautifulSoup(response.content, 'lxml')
            except Exception as e:
                if attempt == 2:
                    raise ScraperError(f"Failed after 3 attempts: {e}")
                time.sleep(5 * (attempt + 1))
    
    def get_article_urls(self) -> list[str]:
        """Override u svakom scraperu"""
        raise NotImplementedError
    
    def parse_article(self, url: str) -> dict:
        """Override u svakom scraperu"""
        raise NotImplementedError
    
    def normalize_text(self, text: str) -> str:
        """Cirilica u latinicu, ciscenje whitespace"""
        return cyrillic_to_latin(text.strip())
    
    def extract_timestamp(self, soup: BeautifulSoup) -> datetime:
        """Pokusaj ekstrakcije timestamps iz meta tagova"""
        for prop in ['og:published_time', 'article:published_time']:
            meta = soup.find('meta', property=prop)
            if meta and meta.get('content'):
                return parse_datetime(meta['content'])
        return None
```

### RSS scraper klasa

```python
class RssScraper(BaseScraper):
    def __init__(self, source_id, source_url, rss_url):
        super().__init__(source_id, source_url)
        self.rss_url = rss_url
    
    def get_article_urls(self) -> list[str]:
        feed = feedparser.parse(self.rss_url)
        return [entry.link for entry in feed.entries]
```

### WordPress scraper klasa

```python
class WordPressScraper(BaseScraper):
    def __init__(self, source_id, source_url, api_base):
        super().__init__(source_id, source_url)
        self.api_base = api_base
    
    def get_articles(self) -> list[dict]:
        response = self.session.get(
            f"{self.api_base}/wp-json/wp/v2/posts",
            params={'per_page': 50, 'orderby': 'date'}
        )
        posts = response.json()
        return [{
            'url': post['link'],
            'title': post['title']['rendered'],
            'text': strip_html(post['content']['rendered']),
            'published_at': post['date_gmt'],
            'modified_at': post['modified_gmt'],
            'author': post.get('_embedded', {}).get('author', [{}])[0].get('name'),
            'categories': [c['name'] for c in post.get('_embedded', {}).get('wp:term', [[]])[0]]
        } for post in posts]
```

---

## 7. Data model za scraping sloj

### Tabela: `articles`

```sql
CREATE TABLE articles (
    id              BIGSERIAL PRIMARY KEY,
    source_id       VARCHAR(50) NOT NULL,  -- 'n1', 'blic', 'informer'...
    url             TEXT NOT NULL UNIQUE,
    title           TEXT NOT NULL,
    subtitle        TEXT,
    text_content    TEXT,
    author          VARCHAR(255),
    published_at    TIMESTAMPTZ,
    scraped_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    content_hash    CHAR(64) NOT NULL,     -- SHA-256
    version         INTEGER NOT NULL DEFAULT 1,
    is_live_blog    BOOLEAN DEFAULT FALSE,
    has_paywall     BOOLEAN DEFAULT FALSE,
    word_count      INTEGER,
    language        CHAR(2) DEFAULT 'sr',
    script          CHAR(4) DEFAULT 'Latn', -- 'Latn' ili 'Cyrl' pre normalizacije
    categories      TEXT[],
    tags            TEXT[],
    raw_html        TEXT,                   -- opciono, za debug
    scraper_version VARCHAR(20)
);

CREATE INDEX idx_articles_source_published ON articles(source_id, published_at DESC);
CREATE INDEX idx_articles_published ON articles(published_at DESC);
CREATE INDEX idx_articles_hash ON articles(content_hash);
```

### Tabela: `article_versions`

```sql
CREATE TABLE article_versions (
    id              BIGSERIAL PRIMARY KEY,
    article_id      BIGINT REFERENCES articles(id),
    title           TEXT NOT NULL,
    text_content    TEXT,
    content_hash    CHAR(64) NOT NULL,
    version         INTEGER NOT NULL,
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

### Tabela: `scraper_runs`

```sql
CREATE TABLE scraper_runs (
    id              BIGSERIAL PRIMARY KEY,
    source_id       VARCHAR(50) NOT NULL,
    started_at      TIMESTAMPTZ NOT NULL,
    finished_at     TIMESTAMPTZ,
    status          VARCHAR(20),  -- 'success', 'partial', 'failed'
    articles_found  INTEGER DEFAULT 0,
    articles_new    INTEGER DEFAULT 0,
    articles_updated INTEGER DEFAULT 0,
    error_type      VARCHAR(50),
    error_message   TEXT,
    consecutive_failures INTEGER DEFAULT 0
);
```

### Tabela: `live_blog_entries`

```sql
CREATE TABLE live_blog_entries (
    id              BIGSERIAL PRIMARY KEY,
    article_id      BIGINT REFERENCES articles(id),
    entry_text      TEXT NOT NULL,
    entry_timestamp TIMESTAMPTZ,
    scraped_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    content_hash    CHAR(64) NOT NULL
);
```

---

## 8. Otvorena pitanja pre implementacije

1. **Playwright vs BeautifulSoup** - Za sajtove koji se ispostave da su JS-rendered, potrebno je odluciti da li koristimo Playwright (tezi, sporiji, vise resursa) ili pronalazimo API endpoint koji oni interno koriste (cesto postoji). Treba proveriti svaki JS sajt pre odluke.

2. **User-Agent politika** - Da li se predstavljamo kao research bot (transparentno) ili simuliramo browser (efikasnije ali manje eticki). Predlog: transparentni User-Agent sa kontakt emailom.

3. **Rate limiting** - Neke platforme mogu da blokiraju pri hourly scraping-u. Treba testirati svaki sajt i eventualno smanjiti frekvenciju za specificne.

4. **Arhiviranje raw HTML** - Da li cuvamo raw HTML svakog clanka za debug i retroaktivno re-parsiranje? Skupo po storage-u ali korisno. Predlog: cuvati 30 dana, zatim brisati.

5. **Paywall handling** - Za sajtove sa paywallom (Blic premium, Danas Klub citalaca), da li pokusavamo da dobijemo pristup ili jednostavno biljezimo `has_paywall: true` i skipujemo? Predlog: skipovati, biljeziti metapodatke.

6. **Tanjug kao poseban slucaj** - Tanjug objavljuje vesti bez autorskog potpisa koje preuzimaju drugi mediji. Treba posebnu logiku za detekciju Tanjug-origin clanaka na drugim portalima.

---

## 9. Sledeci koraci

1. Rucno proveriti tehnicke profile za sve sajtove oznacene sa "POTREBNO PROVERITI RUCNO"
2. Implementirati Base, RSS i WordPress scraper klase
3. Implementirati i testirati prva 4 scraper-a iz Faze 1
4. Verifikovati da content hashing i verzioniranje rade ispravno
5. Implementirati staggered scheduler (APScheduler ili Celery Beat)
6. Implementirati error handling i alert sistem
7. Postepeno dodavati ostale scrapere iz Faza 2 i 3
