-- =====================================================================
-- KEYWORD ĐÃ DUYỆT (nút "LẤY KEYWORD" trên dashboard GitHub Pages)
-- Cách dùng: chạy auth_postgres.sql trước, sau đó dán file này vào Supabase > SQL Editor > Run
-- (chạy lại nhiều lần an toàn).
-- Cơ chế:
--   * Chỉ tài khoản approved = true mới xem / thêm keyword duyệt.
--   * Người duyệt và email được tự điền từ phiên đăng nhập, client không tự khai được.
--   * Mỗi keyword chỉ duyệt 1 lần (không phân biệt hoa thường).
-- =====================================================================

CREATE TABLE IF NOT EXISTS public.approved_keywords (
    id                 BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    keyword            TEXT NOT NULL CHECK (length(btrim(keyword)) BETWEEN 1 AND 300),
    source_keyword     TEXT,                 -- keyword thu thập gốc trên dashboard
    niche              TEXT,                 -- nhóm chủ đề
    intent             TEXT,                 -- loại gợi ý SEO
    based_on           TEXT,                 -- gợi ý dựa trên bài viết nào
    report_date        DATE,                 -- ngày báo cáo chứa keyword
    approved_by        UUID DEFAULT auth.uid() REFERENCES auth.users(id) ON DELETE SET NULL,
    approved_by_email  TEXT DEFAULT (auth.jwt() ->> 'email'),
    approved_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX IF NOT EXISTS approved_keywords_keyword_uniq ON public.approved_keywords (lower(btrim(keyword)));
CREATE INDEX IF NOT EXISTS approved_keywords_approved_at_idx ON public.approved_keywords (approved_at DESC);

ALTER TABLE public.approved_keywords ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "approved_keywords_select_approved" ON public.approved_keywords;
CREATE POLICY "approved_keywords_select_approved" ON public.approved_keywords
    FOR SELECT TO authenticated
    USING (public.is_approved());

DROP POLICY IF EXISTS "approved_keywords_insert_approved" ON public.approved_keywords;
CREATE POLICY "approved_keywords_insert_approved" ON public.approved_keywords
    FOR INSERT TO authenticated
    WITH CHECK (
        public.is_approved()
        AND approved_by = (SELECT auth.uid())
        AND approved_by_email IS NOT DISTINCT FROM (auth.jwt() ->> 'email')
    );

GRANT SELECT, INSERT ON public.approved_keywords TO authenticated;
