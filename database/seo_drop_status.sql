-- =====================================================================
-- Thêm trạng thái 'dropped' (nút "Bỏ" ở tab WORKFLOW) cho outline và bài viết.
--   * Bỏ outline  -> keyword đó dừng, Cowork không lập lại outline / không viết bài.
--   * Bỏ bài viết -> Cowork không viết lại, không cần thêm link bài đăng.
-- Dán vào Supabase > SQL Editor > Run (chạy lại nhiều lần an toàn). Chạy SAU seo_content.sql.
-- Index duy nhất chỉ loại trừ 'rejected', nên bản 'dropped' vẫn chiếm chỗ => Cowork không đẩy trùng lại.
-- =====================================================================
ALTER TABLE public.seo_outlines DROP CONSTRAINT IF EXISTS seo_outlines_status_check;
ALTER TABLE public.seo_outlines ADD CONSTRAINT seo_outlines_status_check
    CHECK (status IN ('pending', 'approved', 'rejected', 'dropped'));

ALTER TABLE public.seo_articles DROP CONSTRAINT IF EXISTS seo_articles_status_check;
ALTER TABLE public.seo_articles ADD CONSTRAINT seo_articles_status_check
    CHECK (status IN ('pending', 'approved', 'rejected', 'dropped'));
