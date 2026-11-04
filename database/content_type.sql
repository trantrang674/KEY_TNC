-- =====================================================================
-- LOẠI NỘI DUNG (content_type) + DỮ LIỆU THỰC CHO BÀI ĐÁNH GIÁ SẢN PHẨM
-- Cách dùng: chạy sau approved_keywords.sql và seo_content.sql, dán file này vào
-- Supabase > SQL Editor > Run (chạy lại nhiều lần an toàn, dữ liệu cũ mặc định là 'news').
-- Quy ước:
--   * content_type = 'news'   -> Cowork dùng skill tnc-viet-bai-tin
--   * content_type = 'review' -> Cowork dùng skill tnc-viet-bai-review
--   * NGƯỜI chọn loại trên dashboard (không để AI đoán). Keyword lấy từ Top 20 tự quét luôn là 'news'.
--   * review_input (JSONB, chỉ dùng cho 'review'): dữ liệu thật do người nhập để AI không bịa:
--       { "product_name": "", "tnc_url": "", "specs": "", "pros": "", "cons": "", "tester_notes": "",
--         "has_hands_on": false, "image_folder": "" }
--     has_hands_on = true khi người nhập xác nhận đã trực tiếp dùng sản phẩm.
-- =====================================================================

-- 1. Cột loại nội dung trên 3 bảng
ALTER TABLE public.approved_keywords ADD COLUMN IF NOT EXISTS content_type TEXT NOT NULL DEFAULT 'news';
ALTER TABLE public.seo_outlines      ADD COLUMN IF NOT EXISTS content_type TEXT NOT NULL DEFAULT 'news';
ALTER TABLE public.seo_articles      ADD COLUMN IF NOT EXISTS content_type TEXT NOT NULL DEFAULT 'news';

-- 2. Dữ liệu thật của bài đánh giá (nằm cùng keyword duyệt)
ALTER TABLE public.approved_keywords ADD COLUMN IF NOT EXISTS review_input JSONB;

-- 3. Ràng buộc giá trị (thêm một lần, chạy lại không lỗi)
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'approved_keywords_content_type_chk') THEN
        ALTER TABLE public.approved_keywords
            ADD CONSTRAINT approved_keywords_content_type_chk CHECK (content_type IN ('news', 'review'));
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'seo_outlines_content_type_chk') THEN
        ALTER TABLE public.seo_outlines
            ADD CONSTRAINT seo_outlines_content_type_chk CHECK (content_type IN ('news', 'review'));
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'seo_articles_content_type_chk') THEN
        ALTER TABLE public.seo_articles
            ADD CONSTRAINT seo_articles_content_type_chk CHECK (content_type IN ('news', 'review'));
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'approved_keywords_review_input_chk') THEN
        ALTER TABLE public.approved_keywords
            ADD CONSTRAINT approved_keywords_review_input_chk
            CHECK (review_input IS NULL OR (jsonb_typeof(review_input) = 'object' AND length(review_input::text) <= 20000));
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS approved_keywords_content_type_idx ON public.approved_keywords (content_type);

-- 4. Người dùng đã duyệt được sửa loại và dữ liệu review của keyword (bổ sung sau khi đã thêm keyword)
DROP POLICY IF EXISTS "approved_keywords_update_approved" ON public.approved_keywords;
CREATE POLICY "approved_keywords_update_approved" ON public.approved_keywords
    FOR UPDATE TO authenticated
    USING (public.is_approved())
    WITH CHECK (public.is_approved());
GRANT UPDATE (content_type, review_input) ON public.approved_keywords TO authenticated;
