-- =====================================================================
-- TNC SEO Keyword News - Schema cho Supabase / PostgreSQL
-- Cách dùng: dán toàn bộ file vào Supabase > SQL Editor > Run.
-- (Nếu hộp thoại hỏi về RLS, chọn "Run and enable RLS" hoặc "Run without RLS" đều được,
--  vì file này đã tự bật RLS cho tất cả các bảng ở cuối.)
-- Chạy lại nhiều lần an toàn (IF NOT EXISTS / ON CONFLICT).
-- =====================================================================

-- ---------- 1. DANH MỤC ----------
CREATE TABLE IF NOT EXISTS niches (
    id           TEXT PRIMARY KEY,
    name         TEXT NOT NULL,
    badge_color  TEXT,
    group_name   TEXT
);

CREATE TABLE IF NOT EXISTS sources (
    id           BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name         TEXT NOT NULL UNIQUE,
    source_type  TEXT NOT NULL CHECK (source_type IN ('PRESS','COMPETITOR','OWN')),
    badge        TEXT,
    domain       TEXT,
    feed_url     TEXT,
    is_active    BOOLEAN NOT NULL DEFAULT TRUE
);

-- ---------- 2. SERPAPI (tạo trước vì report_runs tham chiếu) ----------
CREATE TABLE IF NOT EXISTS serpapi_runs (
    id           BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    run_date     DATE NOT NULL UNIQUE,
    executed_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    forced       BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE TABLE IF NOT EXISTS serpapi_calls (
    id             BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    serpapi_run    BIGINT NOT NULL REFERENCES serpapi_runs(id) ON DELETE CASCADE,
    engine         TEXT NOT NULL CHECK (engine IN
                   ('google_trends_trending_now','google_autocomplete','google','google_trends')),
    query          TEXT,
    status         TEXT NOT NULL,
    result_count   INTEGER,
    error_message  TEXT,
    raw_json       JSONB,
    UNIQUE (serpapi_run, engine)
);

CREATE TABLE IF NOT EXISTS trending_queries (
    id                   BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    call_id              BIGINT NOT NULL REFERENCES serpapi_calls(id) ON DELETE CASCADE,
    query                TEXT NOT NULL,
    search_volume        INTEGER,
    increase_percentage  INTEGER,
    categories           JSONB
);
CREATE TABLE IF NOT EXISTS trending_related_queries (
    trending_id  BIGINT NOT NULL REFERENCES trending_queries(id) ON DELETE CASCADE,
    related      TEXT NOT NULL,
    PRIMARY KEY (trending_id, related)
);

CREATE TABLE IF NOT EXISTS autocomplete_suggestions (
    id          BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    call_id     BIGINT NOT NULL REFERENCES serpapi_calls(id) ON DELETE CASCADE,
    seed        TEXT NOT NULL,
    suggestion  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS google_trends_scores (
    call_id  BIGINT NOT NULL REFERENCES serpapi_calls(id) ON DELETE CASCADE,
    query    TEXT NOT NULL,
    score    INTEGER NOT NULL,
    PRIMARY KEY (call_id, query)
);

CREATE TABLE IF NOT EXISTS serpapi_quota_snapshots (
    id                  BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    captured_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    plan_name           TEXT,
    searches_left       INTEGER,
    searches_per_month  INTEGER,
    this_month_usage    INTEGER
);

-- ---------- 3. BÀI VIẾT ----------
CREATE TABLE IF NOT EXISTS articles (
    id               BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    source_id        BIGINT NOT NULL REFERENCES sources(id),
    url              TEXT NOT NULL UNIQUE,
    title            TEXT NOT NULL,
    title_norm_hash  TEXT,
    summary          TEXT,
    published_at     TIMESTAMPTZ NOT NULL,
    fetched_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    origin           TEXT NOT NULL DEFAULT 'RSS' CHECK (origin IN ('RSS','SERPAPI_SEARCH')),
    niche_id         TEXT REFERENCES niches(id),
    niche_relevance  INTEGER,
    is_noise         BOOLEAN NOT NULL DEFAULT FALSE,
    noise_reason     TEXT
);
CREATE INDEX IF NOT EXISTS idx_articles_published ON articles(published_at DESC);
CREATE INDEX IF NOT EXISTS idx_articles_source    ON articles(source_id);
CREATE INDEX IF NOT EXISTS idx_articles_hash      ON articles(title_norm_hash);
CREATE INDEX IF NOT EXISTS idx_articles_niche     ON articles(niche_id);

-- ---------- 4. KEYWORD ----------
CREATE TABLE IF NOT EXISTS keywords (
    id               BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    cluster_id       TEXT NOT NULL UNIQUE,
    display_keyword  TEXT NOT NULL,
    niche_id         TEXT REFERENCES niches(id),
    first_seen_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_seen_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_keywords_niche ON keywords(niche_id);

CREATE TABLE IF NOT EXISTS article_keywords (
    article_id  BIGINT NOT NULL REFERENCES articles(id) ON DELETE CASCADE,
    keyword_id  BIGINT NOT NULL REFERENCES keywords(id) ON DELETE CASCADE,
    PRIMARY KEY (article_id, keyword_id)
);
CREATE INDEX IF NOT EXISTS idx_ak_keyword ON article_keywords(keyword_id);

-- ---------- 5. BÁO CÁO TOP 10 ----------
CREATE TABLE IF NOT EXISTS report_runs (
    id                      BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    generated_at            TIMESTAMPTZ NOT NULL,
    time_window_hours       INTEGER NOT NULL DEFAULT 48,
    total_articles_scanned  INTEGER,
    total_clusters          INTEGER,
    serpapi_run_id          BIGINT REFERENCES serpapi_runs(id) ON DELETE SET NULL,
    triggered_by            TEXT DEFAULT 'manual'
);
CREATE INDEX IF NOT EXISTS idx_runs_generated ON report_runs(generated_at DESC);

CREATE TABLE IF NOT EXISTS keyword_rankings (
    id                    BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    run_id                BIGINT NOT NULL REFERENCES report_runs(id) ON DELETE CASCADE,
    keyword_id            BIGINT NOT NULL REFERENCES keywords(id),
    rank                  INTEGER NOT NULL,
    total_score           NUMERIC(5,1) NOT NULL,
    score_coverage        NUMERIC(5,1),
    score_competitor      NUMERIC(5,1),
    score_freshness       NUMERIC(5,1),
    score_serpapi_trend   NUMERIC(5,1),
    total_articles_found  INTEGER,
    press_count           INTEGER,
    competitor_count      INTEGER,
    newest_hours_ago      NUMERIC(6,1),
    is_trending_now       BOOLEAN NOT NULL DEFAULT FALSE,
    google_trends_index   INTEGER NOT NULL DEFAULT 0,
    UNIQUE (run_id, keyword_id),
    UNIQUE (run_id, rank)
);
CREATE INDEX IF NOT EXISTS idx_rank_keyword ON keyword_rankings(keyword_id, run_id);

CREATE TABLE IF NOT EXISTS ranking_articles (
    ranking_id  BIGINT NOT NULL REFERENCES keyword_rankings(id) ON DELETE CASCADE,
    article_id  BIGINT NOT NULL REFERENCES articles(id),
    position    SMALLINT NOT NULL CHECK (position BETWEEN 1 AND 5),
    PRIMARY KEY (ranking_id, position)
);
CREATE INDEX IF NOT EXISTS idx_ra_article ON ranking_articles(article_id);

-- ---------- 6. GỢI Ý VIẾT BÀI SEO + TIẾN ĐỘ BIÊN TẬP ----------
CREATE TABLE IF NOT EXISTS seo_suggestions (
    id                BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    ranking_id        BIGINT NOT NULL REFERENCES keyword_rankings(id) ON DELETE CASCADE,
    keyword           TEXT NOT NULL,
    intent            TEXT,
    based_on_article  BIGINT REFERENCES articles(id),
    based_on_text     TEXT,
    status            TEXT NOT NULL DEFAULT 'NEW'
                      CHECK (status IN ('NEW','PLANNED','WRITING','PUBLISHED','SKIPPED')),
    assignee          TEXT,
    published_url     TEXT,
    published_at      TIMESTAMPTZ,
    note              TEXT,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (ranking_id, keyword)
);
CREATE INDEX IF NOT EXISTS idx_seo_status ON seo_suggestions(status);

-- ---------- 7. DỮ LIỆU KHỞI TẠO: 9 NGÁCH ----------
INSERT INTO niches (id, name, badge_color, group_name) VALUES
 ('HARDWARE_COMPONENT',  'Linh kiện - Phần Cứng',      'emerald', 'Sát sườn ngành hàng'),
 ('OS_SOFTWARE',         'HĐH - Phần mềm',    'blue',    'Sát sườn ngành hàng'),
 ('BIG_TECH_EVENT',      'Có thể quan tâm',          'indigo',  'Sát sườn ngành hàng'),
 ('GAME_TREND',          'Game',        'purple',  'Tin tức Hot & Trend'),
 ('AI_UPDATES',          'A.I',        'amber',   'Tin tức Hot & Trend'),
 ('SOCIAL_APPS',         'Mạng xã hội - App',      'pink',    'Tin tức Hot & Trend'),
 ('GOV_DIGITAL_POLICY',  'Chính sách - Quy định',   'red',     'Tin tức Hot & Trend'),
 ('CYBERSECURITY_ALERT', 'An ninh mạng',      'rose',    'Mở rộng hữu ích'),
 ('PC_TIPS_FREE_GAMES',  'Tối ưu - Sửa lỗi',   'teal',    'Mở rộng hữu ích')
ON CONFLICT (id) DO NOTHING;

-- ---------- 8. VIEW: Top 10 của lần chạy mới nhất ----------
CREATE OR REPLACE VIEW v_latest_top10
WITH (security_invoker = true) AS
SELECT kr.rank, k.display_keyword, n.name AS niche, kr.total_score,
       kr.score_coverage, kr.score_competitor, kr.score_freshness, kr.score_serpapi_trend,
       kr.press_count, kr.competitor_count, kr.is_trending_now
FROM keyword_rankings kr
JOIN keywords k ON k.id = kr.keyword_id
LEFT JOIN niches n ON n.id = k.niche_id
WHERE kr.run_id = (SELECT id FROM report_runs ORDER BY generated_at DESC LIMIT 1)
ORDER BY kr.rank;

-- ---------- 9. BẬT ROW LEVEL SECURITY CHO TẤT CẢ BẢNG ----------
-- Không tạo policy => anon/authenticated KHÔNG truy cập được.
-- Backend dùng service_role key (hoặc kết nối Postgres trực tiếp) vẫn đọc/ghi bình thường.
ALTER TABLE niches                    ENABLE ROW LEVEL SECURITY;
ALTER TABLE sources                   ENABLE ROW LEVEL SECURITY;
ALTER TABLE serpapi_runs              ENABLE ROW LEVEL SECURITY;
ALTER TABLE serpapi_calls             ENABLE ROW LEVEL SECURITY;
ALTER TABLE trending_queries          ENABLE ROW LEVEL SECURITY;
ALTER TABLE trending_related_queries  ENABLE ROW LEVEL SECURITY;
ALTER TABLE autocomplete_suggestions  ENABLE ROW LEVEL SECURITY;
ALTER TABLE google_trends_scores      ENABLE ROW LEVEL SECURITY;
ALTER TABLE serpapi_quota_snapshots   ENABLE ROW LEVEL SECURITY;
ALTER TABLE articles                  ENABLE ROW LEVEL SECURITY;
ALTER TABLE keywords                  ENABLE ROW LEVEL SECURITY;
ALTER TABLE article_keywords          ENABLE ROW LEVEL SECURITY;
ALTER TABLE report_runs               ENABLE ROW LEVEL SECURITY;
ALTER TABLE keyword_rankings          ENABLE ROW LEVEL SECURITY;
ALTER TABLE ranking_articles          ENABLE ROW LEVEL SECURITY;
ALTER TABLE seo_suggestions           ENABLE ROW LEVEL SECURITY;
