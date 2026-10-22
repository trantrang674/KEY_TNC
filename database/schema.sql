-- =====================================================================
-- TNC SEO Keyword News - Database schema (SQLite; chạy được trên PostgreSQL
-- nếu đổi INTEGER PRIMARY KEY AUTOINCREMENT -> BIGSERIAL, TEXT(JSON) -> JSONB)
-- Thay thế dần: data/serpapi_daily_*.json, data/latest_top10_report.json
-- Thời gian lưu dạng ISO-8601 có múi giờ +07:00. "hours_ago" KHÔNG lưu, tính lúc truy vấn.
-- =====================================================================
PRAGMA foreign_keys = ON;

-- ---------- 1. DANH MỤC (seed từ classifier.NICHES / news_fetcher.RSS_SOURCES) ----------
CREATE TABLE niches (
    id           TEXT PRIMARY KEY,              -- 'HARDWARE_COMPONENT', 'AI_UPDATES', ...
    name         TEXT NOT NULL,
    badge_color  TEXT,
    group_name   TEXT                           -- 'Sát sườn ngành hàng' | 'Tin tức Hot & Trend' | 'Mở rộng hữu ích'
);

CREATE TABLE sources (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    name         TEXT NOT NULL UNIQUE,          -- 'GenK', 'GearVN', 'CellphoneS (Sforum)'
    source_type  TEXT NOT NULL CHECK (source_type IN ('PRESS','COMPETITOR','OWN')),
    badge        TEXT,
    domain       TEXT,
    feed_url     TEXT,                          -- NULL nếu nguồn chỉ đến từ SerpApi
    is_active    INTEGER NOT NULL DEFAULT 1
);

-- ---------- 2. BÀI VIẾT THU THẬP ----------
CREATE TABLE articles (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id           INTEGER NOT NULL REFERENCES sources(id),
    url                 TEXT NOT NULL UNIQUE,   -- khóa chống trùng chính
    title               TEXT NOT NULL,
    title_norm_hash     TEXT,                   -- hash(\W bỏ, lower, 60 ký tự) - khử trùng theo tiêu đề
    summary             TEXT,
    published_at        TEXT NOT NULL,
    fetched_at          TEXT NOT NULL,
    origin              TEXT NOT NULL DEFAULT 'RSS' CHECK (origin IN ('RSS','SERPAPI_SEARCH')),
    niche_id            TEXT REFERENCES niches(id),
    niche_relevance     INTEGER,
    is_noise            INTEGER NOT NULL DEFAULT 0,   -- bị is_promo_noise / is_smartphone_topic lọc
    noise_reason        TEXT                          -- 'PROMO' | 'SMARTPHONE'
);
CREATE INDEX idx_articles_published ON articles(published_at DESC);
CREATE INDEX idx_articles_source    ON articles(source_id);
CREATE INDEX idx_articles_hash      ON articles(title_norm_hash);

-- ---------- 3. KEYWORD (cụm) ----------
CREATE TABLE keywords (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    cluster_id       TEXT NOT NULL UNIQUE,      -- engine: cluster_id
    display_keyword  TEXT NOT NULL,
    niche_id         TEXT REFERENCES niches(id),
    first_seen_at    TEXT NOT NULL,
    last_seen_at     TEXT NOT NULL
);

-- Bài thuộc cụm nào (1 bài chỉ thuộc 1 cụm, nhưng cụm có thể đổi theo thời gian)
CREATE TABLE article_keywords (
    article_id  INTEGER NOT NULL REFERENCES articles(id) ON DELETE CASCADE,
    keyword_id  INTEGER NOT NULL REFERENCES keywords(id) ON DELETE CASCADE,
    PRIMARY KEY (article_id, keyword_id)
);
CREATE INDEX idx_ak_keyword ON article_keywords(keyword_id);

-- ---------- 4. MỖI LẦN CHẠY BÁO CÁO ----------
CREATE TABLE report_runs (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    generated_at            TEXT NOT NULL,
    time_window_hours       INTEGER NOT NULL DEFAULT 48,
    total_articles_scanned  INTEGER,
    total_clusters          INTEGER,
    serpapi_run_id          INTEGER REFERENCES serpapi_runs(id),
    triggered_by            TEXT DEFAULT 'manual'  -- 'manual' | 'cron' | 'api'
);
CREATE INDEX idx_runs_generated ON report_runs(generated_at DESC);

-- Top 10 của từng lần chạy + điểm (giữ lịch sử để so sánh xu hướng theo ngày)
CREATE TABLE keyword_rankings (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id                INTEGER NOT NULL REFERENCES report_runs(id) ON DELETE CASCADE,
    keyword_id            INTEGER NOT NULL REFERENCES keywords(id),
    rank                  INTEGER NOT NULL,
    total_score           REAL NOT NULL,
    score_coverage        REAL,                 -- tối đa 40
    score_competitor      REAL,                 -- tối đa 25
    score_freshness       REAL,                 -- tối đa 20
    score_serpapi_trend   REAL,                 -- tối đa 15
    total_articles_found  INTEGER,
    press_count           INTEGER,
    competitor_count      INTEGER,
    newest_hours_ago      REAL,
    is_trending_now       INTEGER DEFAULT 0,
    google_trends_index   INTEGER DEFAULT 0,
    UNIQUE (run_id, keyword_id),
    UNIQUE (run_id, rank)
);
CREATE INDEX idx_rank_keyword ON keyword_rankings(keyword_id, run_id);

-- Top 5 bài đại diện cho mỗi keyword trong mỗi lần chạy
CREATE TABLE ranking_articles (
    ranking_id  INTEGER NOT NULL REFERENCES keyword_rankings(id) ON DELETE CASCADE,
    article_id  INTEGER NOT NULL REFERENCES articles(id),
    position    INTEGER NOT NULL CHECK (position BETWEEN 1 AND 5),
    PRIMARY KEY (ranking_id, position)
);

-- ---------- 5. KEYWORD GỢI Ý VIẾT BÀI SEO + KẾ HOẠCH NỘI DUNG ----------
CREATE TABLE seo_suggestions (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    ranking_id        INTEGER NOT NULL REFERENCES keyword_rankings(id) ON DELETE CASCADE,
    keyword           TEXT NOT NULL,
    intent            TEXT,                     -- 'Keyword Hướng dẫn / Thủ thuật', ...
    based_on_article  INTEGER REFERENCES articles(id),
    based_on_text     TEXT,                     -- '[Nguồn] tiêu đề' như engine sinh ra
    -- phần quản lý biên tập (hệ thống hiện chưa có, thêm mới)
    status            TEXT NOT NULL DEFAULT 'NEW'
                      CHECK (status IN ('NEW','PLANNED','WRITING','PUBLISHED','SKIPPED')),
    assignee          TEXT,
    published_url     TEXT,
    published_at      TEXT,
    note              TEXT,
    created_at        TEXT NOT NULL,
    UNIQUE (ranking_id, keyword)
);
CREATE INDEX idx_seo_status ON seo_suggestions(status);

-- ---------- 6. SERPAPI (4 cổng, 1 lượt/ngày) ----------
CREATE TABLE serpapi_runs (                      -- thay serpapi_daily_YYYY-MM-DD.json
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    run_date     TEXT NOT NULL UNIQUE,           -- 'YYYY-MM-DD' (VN) => cache 24h = có dòng này là khỏi gọi lại
    executed_at  TEXT NOT NULL,
    forced       INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE serpapi_calls (                     -- 1 dòng / API / ngày
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    serpapi_run   INTEGER NOT NULL REFERENCES serpapi_runs(id) ON DELETE CASCADE,
    engine        TEXT NOT NULL CHECK (engine IN
                  ('google_trends_trending_now','google_autocomplete','google','google_trends')),
    query         TEXT,                          -- seed / combined query
    status        TEXT NOT NULL,                 -- 'success' | 'http_429' | 'error'
    result_count  INTEGER,
    error_message TEXT,
    raw_json      TEXT,                          -- tuỳ chọn: lưu thô để debug
    UNIQUE (serpapi_run, engine)
);

CREATE TABLE trending_queries (                  -- Google Trends Trending Now
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    call_id             INTEGER NOT NULL REFERENCES serpapi_calls(id) ON DELETE CASCADE,
    query               TEXT NOT NULL,
    search_volume       INTEGER,
    increase_percentage INTEGER,
    categories          TEXT                     -- JSON array: ["Sports"]
);
CREATE TABLE trending_related_queries (
    trending_id  INTEGER NOT NULL REFERENCES trending_queries(id) ON DELETE CASCADE,
    related      TEXT NOT NULL,
    PRIMARY KEY (trending_id, related)
);

CREATE TABLE autocomplete_suggestions (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    call_id    INTEGER NOT NULL REFERENCES serpapi_calls(id) ON DELETE CASCADE,
    seed       TEXT NOT NULL,
    suggestion TEXT NOT NULL
);

CREATE TABLE google_trends_scores (
    call_id  INTEGER NOT NULL REFERENCES serpapi_calls(id) ON DELETE CASCADE,
    query    TEXT NOT NULL,
    score    INTEGER NOT NULL,                   -- trung bình 7 ngày, 0-100
    PRIMARY KEY (call_id, query)
);

-- Quota SerpApi (từ /account.json, miễn phí) - để vẽ biểu đồ dùng quota
CREATE TABLE serpapi_quota_snapshots (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    captured_at         TEXT NOT NULL,
    plan_name           TEXT,
    searches_left       INTEGER,
    searches_per_month  INTEGER,
    this_month_usage    INTEGER
);

-- ---------- 7. VIEW TIỆN DỤNG ----------
-- Top 10 của lần chạy mới nhất (thay cho latest_top10_report.json)
CREATE VIEW v_latest_top10 AS
SELECT kr.rank, k.display_keyword, n.name AS niche, kr.total_score,
       kr.score_coverage, kr.score_competitor, kr.score_freshness, kr.score_serpapi_trend,
       kr.press_count, kr.competitor_count, kr.is_trending_now
FROM keyword_rankings kr
JOIN keywords k ON k.id = kr.keyword_id
LEFT JOIN niches n ON n.id = k.niche_id
WHERE kr.run_id = (SELECT id FROM report_runs ORDER BY generated_at DESC LIMIT 1)
ORDER BY kr.rank;
