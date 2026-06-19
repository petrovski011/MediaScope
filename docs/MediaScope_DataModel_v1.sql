-- ============================================================
-- MediaScope - PostgreSQL Data Model v1.0
-- Jun 2026 | SHARE Fondacija
-- ============================================================
-- Konvencije:
--   - sve tabele imaju id BIGSERIAL PRIMARY KEY
--   - vremenske oznake su TIMESTAMPTZ (sa timezone)
--   - soft delete: deleted_at TIMESTAMPTZ (NULL = aktivan)
--   - audit: created_at, updated_at na svim tabelama
--   - JSONB za fleksibilne meta podatke
-- ============================================================

-- ── EKSTENZIJE ───────────────────────────────────────────────
CREATE EXTENSION IF NOT EXISTS "pgcrypto";       -- gen_random_uuid()
CREATE EXTENSION IF NOT EXISTS "pg_trgm";        -- trigram similarity za copy-paste detekciju
CREATE EXTENSION IF NOT EXISTS "unaccent";       -- normalizacija dijakritika za pretragu
CREATE EXTENSION IF NOT EXISTS "vector";         -- pgvector za embeddings (copy-paste + NER similarity)

-- ============================================================
-- MODUL 1: IZVORI (MEDIJI)
-- ============================================================

CREATE TABLE sources (
    id                  SERIAL PRIMARY KEY,
    source_id           VARCHAR(20) NOT NULL UNIQUE,   -- 'n1', 'blic', 'informer'...
    name                VARCHAR(100) NOT NULL,
    url                 TEXT NOT NULL,
    owner               VARCHAR(200),                  -- vlasnik medija
    owner_group         VARCHAR(100),                  -- 'United Media', 'Ringier', 'Drzavni'...
    media_type          VARCHAR(20),                   -- 'portal', 'tv_portal', 'agency', 'weekly'
    scraper_method      VARCHAR(20),                   -- 'rss', 'html_listing', 'wp_api', 'stub'
    is_active           BOOLEAN NOT NULL DEFAULT TRUE,
    has_timestamp_time  BOOLEAN NOT NULL DEFAULT TRUE, -- FALSE za RTS i Tanjug (samo datum)
    has_author          BOOLEAN NOT NULL DEFAULT TRUE, -- FALSE za Pink, Insajder, RTS, Prva, SD, Radar
    has_category        BOOLEAN NOT NULL DEFAULT TRUE, -- FALSE za Kurir, Insajder, Nova, Politika, Radar
    cloudflare          BOOLEAN NOT NULL DEFAULT FALSE,
    notes               TEXT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Seed podaci za sve izvore
INSERT INTO sources (source_id, name, url, owner, owner_group, media_type, scraper_method, has_timestamp_time, has_author, has_category, cloudflare, notes) VALUES
('n1',        'N1',           'https://n1info.rs',          'United Media',          'United Media',  'portal',     'rss',          TRUE,  TRUE,  TRUE,  TRUE,  'Nema slike na delu clanaka'),
('blic',      'Blic',         'https://www.blic.rs',        'Ringier',               'Strani privatni','portal',     'rss',          TRUE,  TRUE,  TRUE,  FALSE, 'Ring Publishing CMS, 7 RSS feedova'),
('telegraf',  'Telegraf',     'https://www.telegraf.rs',    'Nezavisan',             'Nezavisan',     'portal',     'rss_html',     TRUE,  TRUE,  TRUE,  FALSE, 'Schema.org kompletan'),
('kurir',     'Kurir',        'https://www.kurir.rs',       'Adria Media',           'Strani privatni','portal',     'rss',          TRUE,  TRUE,  FALSE, FALSE, 'Nema category'),
('sd',        'Srbija danas', 'https://www.sd.rs',          'Nezavisan',             'Nezavisan',     'portal',     'rss',          TRUE,  FALSE, TRUE,  FALSE, 'Deo kratkih tekstova'),
('rts',       'RTS',          'https://www.rts.rs',         'Javni servis',          'Drzavni',       'portal',     'html_listing', FALSE, FALSE, TRUE,  FALSE, 'Timestamp bez vremena - samo datum'),
('nova',      'Nova',         'https://nova.rs',            'United Media',          'United Media',  'portal',     'rss',          TRUE,  TRUE,  FALSE, TRUE,  '~13% praznih tekstova'),
('informer',  'Informer',     'https://informer.rs',        'Dragan J. Vucicevic',   'Domaci privatni','portal',     'html_listing', TRUE,  TRUE,  TRUE,  FALSE, 'Komentar count dostupan'),
('danas',     'Danas',        'https://www.danas.rs',       'United Media',          'United Media',  'portal',     'rss',          TRUE,  TRUE,  TRUE,  TRUE,  NULL),
('b92',       'B92',          'https://www.b92.net',        'United Media',          'United Media',  'portal',     'rss',          TRUE,  TRUE,  TRUE,  FALSE, 'Author = rubrika/agencija na delu'),
('mondo',     'Mondo',        'https://mondo.rs',           'Telekom Srbija',        'Telekom',       'portal',     'html_listing', TRUE,  TRUE,  TRUE,  FALSE, 'SSR Nuxt'),
('pink',      'Pink',         'https://pink.rs',            'Pink Media Group',      'Domaci privatni','tv_portal',  'html_listing', TRUE,  FALSE, TRUE,  FALSE, '~20% bez teksta; nema autora'),
('birn',      'BIRN',         'https://birn.rs',            'NGO/Nezavisan',         'NGO',           'portal',     'rss',          TRUE,  TRUE,  TRUE,  TRUE,  'Manji obim, istrazivacki medij'),
('radar',     'Radar',        'https://radar.nova.rs',      'United Media',          'United Media',  'portal',     'wp_api',       TRUE,  FALSE, TRUE,  TRUE,  'Redirect na radar.nova.rs; WordPress'),
('prva',      'Prva TV',      'https://www.prva.rs',        'Antenna Group',         'Strani privatni','tv_portal',  'rss_html',     TRUE,  FALSE, TRUE,  FALSE, 'Nema autora'),
('juzne',     'Juzne vesti',  'https://www.juznevesti.com', 'Regionalni/Nezavisan',  'Nezavisan',     'portal',     'stub',         TRUE,  TRUE,  TRUE,  TRUE,  'STUB - Cloudflare JS challenge'),
('vreme',     'Vreme',        'https://www.vreme.rs',       'Nezavisan',             'Nezavisan',     'weekly',     'rss',          TRUE,  TRUE,  TRUE,  TRUE,  'Nedeljnik - 15-20 clanaka nedeljno'),
('insajder',  'Insajder',     'https://insajder.net',       'Nezavisan',             'Nezavisan',     'portal',     'rss',          TRUE,  FALSE, FALSE, TRUE,  'Nema autora ni category'),
('tanjug',    'Tanjug',       'https://www.tanjug.rs',      'Drzava',                'Drzavni',       'agency',     'html_listing', FALSE, TRUE,  TRUE,  FALSE, 'Timestamp bez vremena; kljucan za origin tracking'),
('politika',  'Politika',     'https://www.politika.rs',    'Drzava/PKB',            'Drzavni',       'portal',     'html_listing', TRUE,  TRUE,  TRUE,  FALSE, 'Rate-limit na bulk fetchu');

-- ============================================================
-- MODUL 2: CLANCI
-- ============================================================

CREATE TABLE articles (
    id                  BIGSERIAL PRIMARY KEY,
    source_id           VARCHAR(20) NOT NULL REFERENCES sources(source_id),
    url                 TEXT NOT NULL,
    url_hash            CHAR(64) NOT NULL,             -- SHA-256 url-a za brzu pretragu
    content_hash        CHAR(64) NOT NULL,             -- SHA-256 title+text za deduplication
    version             INTEGER NOT NULL DEFAULT 1,    -- verzija clanka (raste pri izmeni)

    -- Sadrzaj
    title               TEXT NOT NULL,
    subtitle            TEXT,                          -- dostupno na ~54% korpusa
    text_content        TEXT,                          -- ociscen tekst, bez HTML
    text_raw            TEXT,                          -- originalni HTML pre ciscenja
    word_count          INTEGER,                       -- broj reci u text_content

    -- Meta
    author              VARCHAR(500),                  -- NULL na 6 izvora
    published_at        TIMESTAMPTZ,                   -- NULL na ~2.6% korpusa
    updated_at          TIMESTAMPTZ,                   -- samo ~23% ima
    category            VARCHAR(200),                  -- NULL na 5 izvora
    tags                TEXT[],                        -- array, NULL tamo gde nema
    image_url           TEXT,                          -- NULL na N1 i delu ostalih
    image_caption       TEXT,                          -- retko dostupno
    comment_count       INTEGER,                       -- samo Informer konzistentno

    -- Scraping meta
    scraped_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    scraper_version     VARCHAR(20),

    -- Flags
    has_paywall         BOOLEAN NOT NULL DEFAULT FALSE,
    is_live_blog        BOOLEAN NOT NULL DEFAULT FALSE,
    language            CHAR(2) NOT NULL DEFAULT 'sr',
    script              CHAR(4) NOT NULL DEFAULT 'Latn', -- 'Latn' ili 'Cyrl' pre normalizacije

    -- Schema.org raw data
    schema_data         JSONB,                         -- raw JSON-LD ako postoji

    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Indexi za articles
CREATE UNIQUE INDEX idx_articles_url_hash ON articles(url_hash);
CREATE INDEX idx_articles_source_published ON articles(source_id, published_at DESC);
CREATE INDEX idx_articles_published ON articles(published_at DESC);
CREATE INDEX idx_articles_content_hash ON articles(content_hash);
CREATE INDEX idx_articles_scraped ON articles(scraped_at DESC);
CREATE INDEX idx_articles_source_scraped ON articles(source_id, scraped_at DESC);
-- Full text search
CREATE INDEX idx_articles_title_trgm ON articles USING gin(title gin_trgm_ops);
CREATE INDEX idx_articles_text_trgm ON articles USING gin(text_content gin_trgm_ops);
-- Tags array search
CREATE INDEX idx_articles_tags ON articles USING gin(tags);

-- ── Verzioniranje clanaka ─────────────────────────────────────
CREATE TABLE article_versions (
    id                  BIGSERIAL PRIMARY KEY,
    article_id          BIGINT NOT NULL REFERENCES articles(id),
    version             INTEGER NOT NULL,
    title               TEXT NOT NULL,
    subtitle            TEXT,
    text_content        TEXT,
    text_raw            TEXT,
    content_hash        CHAR(64) NOT NULL,
    changed_fields      TEXT[],                        -- koja polja su se promenila
    changed_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(article_id, version)
);

CREATE INDEX idx_article_versions_article ON article_versions(article_id);

-- ── Scraper runs log ──────────────────────────────────────────
CREATE TABLE scraper_runs (
    id                  BIGSERIAL PRIMARY KEY,
    source_id           VARCHAR(20) NOT NULL REFERENCES sources(source_id),
    started_at          TIMESTAMPTZ NOT NULL,
    finished_at         TIMESTAMPTZ,
    status              VARCHAR(20),                   -- 'success', 'partial', 'failed'
    articles_found      INTEGER DEFAULT 0,
    articles_new        INTEGER DEFAULT 0,
    articles_updated    INTEGER DEFAULT 0,
    articles_skipped    INTEGER DEFAULT 0,
    error_type          VARCHAR(50),
    error_message       TEXT,
    consecutive_failures INTEGER DEFAULT 0,
    duration_ms         INTEGER
);

CREATE INDEX idx_scraper_runs_source ON scraper_runs(source_id, started_at DESC);
CREATE INDEX idx_scraper_runs_status ON scraper_runs(status, started_at DESC);

-- ============================================================
-- MODUL 3: AI ANALIZA
-- ============================================================

-- ── Analiza clanka ────────────────────────────────────────────
CREATE TABLE article_analysis (
    id                  BIGSERIAL PRIMARY KEY,
    article_id          BIGINT NOT NULL REFERENCES articles(id),

    -- Tematska klasifikacija
    topics              TEXT[],                        -- lista tema ['politika', 'EU', 'protest']
    primary_topic       VARCHAR(200),                  -- glavna tema
    topic_confidence    FLOAT,                         -- 0-1

    -- Pozicioniranje na osama
    political_score     FLOAT,                         -- -1.0 (opozicija) do +1.0 (pro-vlada)
    value_score         FLOAT,                         -- -1.0 (progresivno) do +1.0 (konzervativno)
    sensationalism      FLOAT,                         -- 0-1

    -- Sentiment
    sentiment           VARCHAR(20),                   -- 'positive', 'negative', 'neutral'
    sentiment_score     FLOAT,                         -- -1.0 do +1.0

    -- Framing (vise framinga po clanku)
    -- -> veza kroz article_framings tabelu

    -- Narativ (vise narativa po clanku)
    -- -> veza kroz article_narratives tabelu

    -- Meta
    model_used          VARCHAR(50),                   -- 'claude-haiku-4-5'
    model_version       VARCHAR(20),
    analysis_version    VARCHAR(20),                   -- verzija AI pipeline-a
    analyzed_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    tokens_used         INTEGER,

    -- Objasnjenje (transparentnost)
    topic_explanation   TEXT,                          -- zasto je ovako klasifikovan
    political_explanation TEXT,
    value_explanation   TEXT,

    -- Kalibracija
    calibration_applied BOOLEAN DEFAULT FALSE,
    calibration_notes   TEXT,

    UNIQUE(article_id)
);

CREATE INDEX idx_analysis_article ON article_analysis(article_id);
CREATE INDEX idx_analysis_political ON article_analysis(political_score);
CREATE INDEX idx_analysis_analyzed ON article_analysis(analyzed_at DESC);
CREATE INDEX idx_analysis_topic ON article_analysis USING gin(topics);

-- ── NER entiteti ──────────────────────────────────────────────
CREATE TABLE entities (
    id                  BIGSERIAL PRIMARY KEY,
    name                VARCHAR(500) NOT NULL,          -- normalizovano ime
    name_variants       TEXT[],                         -- varijante: 'Vucic', 'Aleksandar Vucic', 'predsednik'
    entity_type         VARCHAR(20) NOT NULL,           -- 'person', 'organization', 'location'
    is_political_actor  BOOLEAN DEFAULT FALSE,
    description         TEXT,                           -- kratki opis
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX idx_entities_name_type ON entities(name, entity_type);
CREATE INDEX idx_entities_type ON entities(entity_type);
CREATE INDEX idx_entities_political ON entities(is_political_actor) WHERE is_political_actor = TRUE;

-- ── Pominjanja entiteta u clancima ───────────────────────────
CREATE TABLE article_entities (
    id                  BIGSERIAL PRIMARY KEY,
    article_id          BIGINT NOT NULL REFERENCES articles(id),
    entity_id           BIGINT NOT NULL REFERENCES entities(id),
    mention_count       INTEGER NOT NULL DEFAULT 1,
    is_quoted           BOOLEAN DEFAULT FALSE,          -- da li se akter citira direktno
    is_subject          BOOLEAN DEFAULT FALSE,          -- da li je akter subjekt clanka
    context_snippet     TEXT,                           -- kratki kontekst oko pomena
    UNIQUE(article_id, entity_id)
);

CREATE INDEX idx_article_entities_article ON article_entities(article_id);
CREATE INDEX idx_article_entities_entity ON article_entities(entity_id);

-- ── Framing tipovi ────────────────────────────────────────────
CREATE TABLE framing_types (
    id                  SERIAL PRIMARY KEY,
    name                VARCHAR(200) NOT NULL,
    topic_id            INTEGER,                        -- NULL = globalni framing, int = tematski specifican
    description         TEXT,
    created_by          INTEGER,                        -- REFERENCES users(id)
    is_validated        BOOLEAN DEFAULT FALSE,          -- da li je validiran od strane istrazivaca
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_framing_types_topic ON framing_types(topic_id);

-- ── Framing po clanku ─────────────────────────────────────────
CREATE TABLE article_framings (
    id                  BIGSERIAL PRIMARY KEY,
    article_id          BIGINT NOT NULL REFERENCES articles(id),
    framing_type_id     INTEGER NOT NULL REFERENCES framing_types(id),
    confidence          FLOAT,                         -- 0-1 skor poverenja
    supporting_text     TEXT,                          -- delovi teksta koji podupiru framing
    UNIQUE(article_id, framing_type_id)
);

CREATE INDEX idx_article_framings_article ON article_framings(article_id);
CREATE INDEX idx_article_framings_framing ON article_framings(framing_type_id);

-- ── Narativi ──────────────────────────────────────────────────
CREATE TABLE narratives (
    id                  SERIAL PRIMARY KEY,
    name                VARCHAR(300) NOT NULL,
    narrative_type      VARCHAR(20) NOT NULL,           -- 'systemic' ili 'thematic'
    description         TEXT,
    is_active           BOOLEAN DEFAULT TRUE,
    is_validated        BOOLEAN DEFAULT FALSE,
    detected_at         TIMESTAMPTZ,                   -- kada je AI prvi put detektovao
    validated_at        TIMESTAMPTZ,                   -- kada je istrazivac validirao
    validated_by        INTEGER,                        -- REFERENCES users(id)
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_narratives_type ON narratives(narrative_type);
CREATE INDEX idx_narratives_active ON narratives(is_active);

-- ── Mapiranje clanaka na narative ─────────────────────────────
CREATE TABLE article_narratives (
    id                  BIGSERIAL PRIMARY KEY,
    article_id          BIGINT NOT NULL REFERENCES articles(id),
    narrative_id        INTEGER NOT NULL REFERENCES narratives(id),
    confidence          FLOAT,
    supporting_text     TEXT,
    UNIQUE(article_id, narrative_id)
);

CREATE INDEX idx_article_narratives_article ON article_narratives(article_id);
CREATE INDEX idx_article_narratives_narrative ON article_narratives(narrative_id);

-- ── Dnevni intenzitet narativa ────────────────────────────────
CREATE TABLE narrative_daily_intensity (
    id                  BIGSERIAL PRIMARY KEY,
    narrative_id        INTEGER NOT NULL REFERENCES narratives(id),
    source_id           VARCHAR(20) REFERENCES sources(source_id),  -- NULL = agregat svih izvora
    date                DATE NOT NULL,
    article_count       INTEGER NOT NULL DEFAULT 0,
    avg_confidence      FLOAT,
    intensity_score     FLOAT,                         -- normalizovani intenzitet 0-1
    UNIQUE(narrative_id, source_id, date)
);

CREATE INDEX idx_narrative_intensity_date ON narrative_daily_intensity(date DESC);
CREATE INDEX idx_narrative_intensity_narrative ON narrative_daily_intensity(narrative_id, date DESC);

-- ============================================================
-- MODUL 4: KOORDINACIJA
-- ============================================================

-- ── Copy-paste detekcija ──────────────────────────────────────
CREATE TABLE coordination_copypaste (
    id                  BIGSERIAL PRIMARY KEY,
    article_id_a        BIGINT NOT NULL REFERENCES articles(id),
    article_id_b        BIGINT NOT NULL REFERENCES articles(id),
    similarity_score    FLOAT NOT NULL,                -- cosine similarity 0-1
    same_owner_group    BOOLEAN,                       -- isti vlasnik = drugacija interpretacija
    detected_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (article_id_a < article_id_b)                -- spreci duplikate (a,b) i (b,a)
);

CREATE INDEX idx_copypaste_score ON coordination_copypaste(similarity_score DESC);
CREATE INDEX idx_copypaste_article_a ON coordination_copypaste(article_id_a);
CREATE INDEX idx_copypaste_article_b ON coordination_copypaste(article_id_b);

-- ── Framing koordinacija ──────────────────────────────────────
CREATE TABLE coordination_framing (
    id                  BIGSERIAL PRIMARY KEY,
    framing_type_id     INTEGER NOT NULL REFERENCES framing_types(id),
    source_ids          TEXT[] NOT NULL,               -- koji mediji koordinisu
    date                DATE NOT NULL,
    hour_window         INTEGER,                       -- u kom vremenskom prozoru (sati)
    article_count       INTEGER NOT NULL,
    coordination_score  FLOAT NOT NULL,
    same_owner_group    BOOLEAN,
    detected_at         TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_framing_coord_date ON coordination_framing(date DESC);
CREATE INDEX idx_framing_coord_score ON coordination_framing(coordination_score DESC);

-- ── Narativna koordinacija ────────────────────────────────────
CREATE TABLE coordination_narrative (
    id                  BIGSERIAL PRIMARY KEY,
    narrative_id        INTEGER NOT NULL REFERENCES narratives(id),
    source_ids          TEXT[] NOT NULL,
    date                DATE NOT NULL,
    hour_window         INTEGER,
    article_count       INTEGER NOT NULL,
    coordination_score  FLOAT NOT NULL,
    same_owner_group    BOOLEAN,
    detected_at         TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_narrative_coord_date ON coordination_narrative(date DESC);
CREATE INDEX idx_narrative_coord_score ON coordination_narrative(coordination_score DESC);

-- ── Alertovi ──────────────────────────────────────────────────
CREATE TABLE alerts (
    id                  BIGSERIAL PRIMARY KEY,
    alert_type          VARCHAR(50) NOT NULL,          -- 'copypaste', 'framing_coord', 'narrative_coord', 'anomaly', 'silence'
    severity            VARCHAR(20) NOT NULL,          -- 'high', 'medium', 'low'
    title               VARCHAR(500) NOT NULL,
    description         TEXT,
    score               FLOAT,                         -- skor koji je triggrovao alert
    source_ids          TEXT[],                        -- ukljuceni mediji
    related_ids         JSONB,                         -- veze na article_id, narrative_id itd.
    date                DATE NOT NULL,
    is_read             BOOLEAN DEFAULT FALSE,
    read_by             INTEGER,                       -- REFERENCES users(id)
    read_at             TIMESTAMPTZ,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_alerts_date ON alerts(date DESC);
CREATE INDEX idx_alerts_type ON alerts(alert_type, date DESC);
CREATE INDEX idx_alerts_unread ON alerts(is_read) WHERE is_read = FALSE;
CREATE INDEX idx_alerts_severity ON alerts(severity, date DESC);

-- ============================================================
-- MODUL 5: ANOMALIJE
-- ============================================================

CREATE TABLE anomalies (
    id                  BIGSERIAL PRIMARY KEY,
    anomaly_type        VARCHAR(50) NOT NULL,          -- 'topic_spike', 'topic_drop', 'framing_shift', 'narrative_break', 'silence', 'sync'
    description         TEXT NOT NULL,
    source_id           VARCHAR(20) REFERENCES sources(source_id),  -- NULL = vise izvora
    topic               VARCHAR(200),
    narrative_id        INTEGER REFERENCES narratives(id),
    date                DATE NOT NULL,
    baseline_value      FLOAT,                         -- baseline vrednost
    detected_value      FLOAT,                         -- detektovana vrednost
    deviation_pct       FLOAT,                         -- % odstupanja od baseline
    baseline_type       VARCHAR(20),                   -- 'rolling_7d', 'rolling_30d'
    alert_id            BIGINT REFERENCES alerts(id),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_anomalies_date ON anomalies(date DESC);
CREATE INDEX idx_anomalies_type ON anomalies(anomaly_type, date DESC);

-- ============================================================
-- MODUL 6: ORIGIN TRACKING
-- ============================================================

CREATE TABLE origin_tracking (
    id                  BIGSERIAL PRIMARY KEY,
    topic               VARCHAR(200) NOT NULL,
    first_article_id    BIGINT NOT NULL REFERENCES articles(id),  -- prvi clanak o temi
    first_source_id     VARCHAR(20) NOT NULL REFERENCES sources(source_id),
    first_published_at  TIMESTAMPTZ NOT NULL,
    has_exact_time      BOOLEAN NOT NULL DEFAULT TRUE,            -- FALSE za RTS/Tanjug
    total_coverage      INTEGER,                                   -- koliko medija je pokrilo
    spread_hours        FLOAT,                                     -- za koliko sati se prosirilo
    narrative_id        INTEGER REFERENCES narratives(id),
    detected_at         TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_origin_topic ON origin_tracking(topic);
CREATE INDEX idx_origin_date ON origin_tracking(first_published_at DESC);
CREATE INDEX idx_origin_source ON origin_tracking(first_source_id);

-- ============================================================
-- MODUL 7: KALIBRACIJA
-- ============================================================

CREATE TABLE calibration_feedback (
    id                  BIGSERIAL PRIMARY KEY,
    user_id             INTEGER NOT NULL,              -- REFERENCES users(id)
    article_id          BIGINT NOT NULL REFERENCES articles(id),
    analysis_type       VARCHAR(50) NOT NULL,          -- 'topic', 'framing', 'narrative', 'political_score', 'value_score'
    is_correct          BOOLEAN NOT NULL,              -- thumbs up / thumbs down
    comment             TEXT,                          -- obavezno uz thumbs down
    original_value      TEXT,                          -- originalna AI vrednost
    corrected_value     TEXT,                          -- ispravljena vrednost (kod thumbs down)
    applied_to_pipeline BOOLEAN DEFAULT FALSE,         -- da li je primenjeno na kalibracioni prompt
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_calibration_user ON calibration_feedback(user_id);
CREATE INDEX idx_calibration_article ON calibration_feedback(article_id);
CREATE INDEX idx_calibration_type ON calibration_feedback(analysis_type, is_correct);
CREATE INDEX idx_calibration_unapplied ON calibration_feedback(applied_to_pipeline) WHERE applied_to_pipeline = FALSE;

-- ── Kalibracioni prompt verzije ───────────────────────────────
CREATE TABLE calibration_prompts (
    id                  SERIAL PRIMARY KEY,
    analysis_type       VARCHAR(50) NOT NULL,
    version             INTEGER NOT NULL,
    prompt_text         TEXT NOT NULL,
    feedback_count      INTEGER DEFAULT 0,             -- koliko feedbackova je ugradeno
    is_active           BOOLEAN DEFAULT TRUE,
    activated_at        TIMESTAMPTZ,
    created_by          INTEGER,                       -- REFERENCES users(id)
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(analysis_type, version)
);

-- ============================================================
-- MODUL 8: KORISNICI I PRISTUPI
-- ============================================================

CREATE TABLE users (
    id                  SERIAL PRIMARY KEY,
    email               VARCHAR(200) NOT NULL UNIQUE,
    name                VARCHAR(200) NOT NULL,
    hashed_password     VARCHAR(200) NOT NULL DEFAULT '',
    role                VARCHAR(20) NOT NULL DEFAULT 'viewer',  -- 'admin', 'researcher', 'viewer'
    is_active           BOOLEAN DEFAULT TRUE,
    last_login          TIMESTAMPTZ,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Dodaj FK-ove koji referenciraju users (dodati posle kreiranja users tabele)
ALTER TABLE framing_types ADD CONSTRAINT fk_framing_created_by FOREIGN KEY (created_by) REFERENCES users(id);
ALTER TABLE narratives ADD CONSTRAINT fk_narrative_validated_by FOREIGN KEY (validated_by) REFERENCES users(id);
ALTER TABLE calibration_feedback ADD CONSTRAINT fk_calibration_user FOREIGN KEY (user_id) REFERENCES users(id);
ALTER TABLE calibration_prompts ADD CONSTRAINT fk_calibration_prompt_user FOREIGN KEY (created_by) REFERENCES users(id);
ALTER TABLE alerts ADD CONSTRAINT fk_alert_read_by FOREIGN KEY (read_by) REFERENCES users(id);

-- ── Watchliste ─────────────────────────────────────────────────
CREATE TABLE watchlists (
    id                  SERIAL PRIMARY KEY,
    user_id             INTEGER NOT NULL REFERENCES users(id),
    name                VARCHAR(200) NOT NULL,
    description         TEXT,
    is_active           BOOLEAN DEFAULT TRUE,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE watchlist_items (
    id                  BIGSERIAL PRIMARY KEY,
    watchlist_id        INTEGER NOT NULL REFERENCES watchlists(id) ON DELETE CASCADE,
    item_type           VARCHAR(30) NOT NULL,          -- 'source', 'entity', 'topic', 'narrative', 'framing_type', 'keyword'
    item_id             INTEGER,                       -- id u odgovarajucoj tabeli (nullable za keyword)
    item_value          TEXT,                          -- za keyword watchliste
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(watchlist_id, item_type, item_id)
);

CREATE INDEX idx_watchlist_items_list ON watchlist_items(watchlist_id);

-- ── Sacuvane pretrage ─────────────────────────────────────────
CREATE TABLE saved_searches (
    id                  SERIAL PRIMARY KEY,
    user_id             INTEGER NOT NULL REFERENCES users(id),
    name                VARCHAR(200),
    query_params        JSONB NOT NULL,                -- svi parametri pretrage
    last_run            TIMESTAMPTZ,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_saved_searches_user ON saved_searches(user_id);

-- ============================================================
-- MODUL 9: EMBEDDINGS (za copy-paste i similarity)
-- ============================================================

CREATE TABLE article_embeddings (
    id                  BIGSERIAL PRIMARY KEY,
    article_id          BIGINT NOT NULL REFERENCES articles(id) UNIQUE,
    embedding           vector(1536),                  -- OpenAI/Anthropic embedding dimenzija
    model_used          VARCHAR(100),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- HNSW index za brzu similarity pretragu
CREATE INDEX idx_embeddings_vector ON article_embeddings
    USING hnsw (embedding vector_cosine_ops);

-- ============================================================
-- MODUL 10: JUTARNJI REZIME
-- ============================================================

CREATE TABLE daily_summaries (
    id                  BIGSERIAL PRIMARY KEY,
    date                DATE NOT NULL UNIQUE,
    summary_text        TEXT NOT NULL,                 -- AI generisani executive summary
    top_topics          TEXT[],
    top_narratives      INTEGER[],                     -- narrative IDs
    alert_count         INTEGER DEFAULT 0,
    article_count       INTEGER DEFAULT 0,
    coordination_alerts INTEGER DEFAULT 0,
    anomaly_count       INTEGER DEFAULT 0,
    model_used          VARCHAR(50),
    generated_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ============================================================
-- POMOCNI VIEWOVI
-- ============================================================

-- Pregled clanaka sa analizom
CREATE VIEW v_articles_with_analysis AS
SELECT
    a.id,
    a.source_id,
    s.name as source_name,
    s.owner_group,
    a.title,
    a.subtitle,
    a.word_count,
    a.author,
    a.published_at,
    a.category,
    a.tags,
    a.has_paywall,
    aa.topics,
    aa.primary_topic,
    aa.political_score,
    aa.value_score,
    aa.sensationalism,
    aa.sentiment,
    aa.analyzed_at,
    s.has_timestamp_time
FROM articles a
JOIN sources s ON a.source_id = s.source_id
LEFT JOIN article_analysis aa ON a.id = aa.article_id;

-- Dnevna statistika po izvoru
CREATE VIEW v_daily_source_stats AS
SELECT
    source_id,
    DATE(published_at) as date,
    COUNT(*) as article_count,
    AVG(aa.political_score) as avg_political_score,
    AVG(aa.value_score) as avg_value_score,
    AVG(aa.sensationalism) as avg_sensationalism
FROM articles a
LEFT JOIN article_analysis aa ON a.id = aa.article_id
WHERE published_at IS NOT NULL
GROUP BY source_id, DATE(published_at);

-- Aktivni neocitani alertovi
CREATE VIEW v_active_alerts AS
SELECT
    a.*,
    s.name as source_names
FROM alerts a,
     LATERAL (
         SELECT string_agg(src.name, ', ') as name
         FROM sources src
         WHERE src.source_id = ANY(a.source_ids)
     ) s
WHERE a.is_read = FALSE
ORDER BY a.severity DESC, a.created_at DESC;

-- ============================================================
-- TRIGERI
-- ============================================================

-- Auto-update updated_at
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_sources_updated_at
    BEFORE UPDATE ON sources
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER trg_users_updated_at
    BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER trg_narratives_updated_at
    BEFORE UPDATE ON narratives
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

-- Automatski izracunaj word_count
CREATE OR REPLACE FUNCTION calc_word_count()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.text_content IS NOT NULL THEN
        NEW.word_count = array_length(regexp_split_to_array(trim(NEW.text_content), '\s+'), 1);
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_articles_word_count
    BEFORE INSERT OR UPDATE OF text_content ON articles
    FOR EACH ROW EXECUTE FUNCTION calc_word_count();

-- ============================================================
-- KOMENTARI
-- ============================================================
COMMENT ON TABLE sources IS 'Registar svih 20 medijskih izvora sa tehnickim i vlasnickim metapodacima';
COMMENT ON TABLE articles IS 'Prikupljeni clanci - osnovna tabela platforme. ~3000 clanaka dnevno pri punom kapacitetu';
COMMENT ON TABLE article_versions IS 'Istorija izmena clanaka. Cuva sve verzije kada scraper detektuje promenu content_hash';
COMMENT ON TABLE article_analysis IS 'AI analiza svakog clanka - teme, pozicioniranje, sentiment. 1:1 sa articles';
COMMENT ON TABLE entities IS 'NER entiteti - osobe, organizacije, mesta. Normalizovani sa varijantama';
COMMENT ON TABLE article_entities IS 'Veza clanak-entitet sa kontekstom pominjanja';
COMMENT ON TABLE framing_types IS 'Tematski specificni framing tipovi. AI predlaze, istrazivac validira';
COMMENT ON TABLE narratives IS 'Narativi - sistemski i tematski. Seeding iz istorijskih podataka';
COMMENT ON TABLE narrative_daily_intensity IS 'Dnevni intenzitet narativa po izvoru - osnova za longitudinalnu analizu';
COMMENT ON TABLE coordination_copypaste IS 'Detektovani copy-paste parovi sa similarity scorom';
COMMENT ON TABLE alerts IS 'Svi alertovi platforme - koordinacija, anomalije, silence';
COMMENT ON TABLE calibration_feedback IS 'RLHF feedback istrazivaca za kalibraciju AI modela';
COMMENT ON TABLE article_embeddings IS 'Vektorski embeddinzi clanaka za similarity search (copy-paste detekcija)';
COMMENT ON COLUMN articles.political_score IS 'Cuvati u article_analysis, ne direktno u articles';
COMMENT ON COLUMN sources.has_timestamp_time IS 'FALSE za RTS i Tanjug - iskljuciti iz intra-day analize';
