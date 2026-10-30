-- =====================================================================
-- SỐ ĐO THẬT (Google Search Console + GA4) của từng bài đã đăng, hiển thị ở tab BÁO CÁO
-- Cách dùng: chạy seo_content.sql trước, sau đó dán file này vào Supabase > SQL Editor > Run (chạy lại nhiều lần an toàn).
-- Cơ chế:
--   * Chỉ script sync_gsc_ga4.py (service_role) ghi dữ liệu; dashboard chỉ đọc.
--   * Chỉ tài khoản approved = true mới xem được (RLS giống seo_articles).
--   * Mỗi bài đã đăng (seo_articles.published_url) có đúng 1 dòng, được ghi đè mỗi lần đồng bộ.
-- =====================================================================

CREATE TABLE IF NOT EXISTS public.seo_article_metrics (
    url             TEXT PRIMARY KEY,                       -- đúng published_url của bài
    article_id      BIGINT REFERENCES public.seo_articles(id) ON DELETE SET NULL,
    daily           JSONB NOT NULL DEFAULT '[]'::jsonb,     -- [{d:'2026-10-25', c:clicks, i:impressions, p:vị trí TB}], 90 ngày gần nhất
    queries         JSONB NOT NULL DEFAULT '[]'::jsonb,     -- top query 28 ngày: [{query, clicks, impr, ctr, rank}]
    device          JSONB NOT NULL DEFAULT '{}'::jsonb,     -- {mobile: %, desktop: %, tablet: %} theo clicks 28 ngày
    ga4             JSONB NOT NULL DEFAULT '{}'::jsonb,     -- {"7d": {sessions, engagement_rate, avg_duration, key_events}, "28d": {...}}
    is_indexed      BOOLEAN,                                -- null = chưa kiểm tra được
    index_state     TEXT,                                   -- coverageState từ URL Inspection API
    last_crawl_time TIMESTAMPTZ,
    data_end_date   DATE,                                   -- ngày cuối cùng GSC đã có số liệu
    synced_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS seo_article_metrics_article_idx ON public.seo_article_metrics (article_id);

-- Bài của cả trang (danh mục Tin tức), không chỉ bài từ dashboard
ALTER TABLE public.seo_article_metrics ADD COLUMN IF NOT EXISTS title          TEXT;
ALTER TABLE public.seo_article_metrics ADD COLUMN IF NOT EXISTS published_date DATE;     -- ngày đăng ghi trên trang danh mục
ALTER TABLE public.seo_article_metrics ADD COLUMN IF NOT EXISTS category       TEXT;     -- danh mục tin tức chứa bài
ALTER TABLE public.seo_article_metrics ADD COLUMN IF NOT EXISTS is_dashboard   BOOLEAN NOT NULL DEFAULT false;  -- true = bài của Cowork dashboard

ALTER TABLE public.seo_article_metrics ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "seo_article_metrics_select_approved" ON public.seo_article_metrics;
CREATE POLICY "seo_article_metrics_select_approved" ON public.seo_article_metrics
    FOR SELECT TO authenticated USING (public.is_approved());

REVOKE ALL ON public.seo_article_metrics FROM anon, authenticated;
GRANT SELECT ON public.seo_article_metrics TO authenticated;
