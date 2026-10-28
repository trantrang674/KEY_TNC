-- =====================================================================
-- OUTLINE + BÀI VIẾT SEO do Cowork (agent skill tnc-seo-content) tạo, chờ người duyệt trên dashboard
-- Cách dùng: chạy auth_postgres.sql và approved_keywords.sql trước, sau đó dán file này vào
-- Supabase > SQL Editor > Run (chạy lại nhiều lần an toàn).
-- Luồng:
--   approved_keywords -> seo_outlines (pending) --[người bấm DUYỆT]--> seo_articles (pending) --[người bấm DUYỆT]--> approved
-- Cơ chế:
--   * Cowork ghi dữ liệu qua Edge Function cowork-api (service_role), không ghi trực tiếp.
--   * Chỉ tài khoản approved = true mới xem / duyệt / sửa outline và bài viết.
--   * Người duyệt và thời điểm duyệt do trigger tự điền từ phiên đăng nhập.
-- =====================================================================

CREATE TABLE IF NOT EXISTS public.seo_outlines (
    id                   BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    approved_keyword_id  BIGINT REFERENCES public.approved_keywords(id) ON DELETE SET NULL,
    keyword              TEXT NOT NULL,
    outline_md           TEXT NOT NULL,            -- dàn ý: title đề xuất, mở đầu, H2/H3, FAQ, kết luận
    short_kws            JSONB NOT NULL DEFAULT '[]'::jsonb,   -- key phụ ngắn (3-4 từ)
    long_kws             JSONB NOT NULL DEFAULT '[]'::jsonb,   -- key phụ dài (5-7 từ)
    research             JSONB,                    -- PAA, đối thủ top Google... (tham khảo)
    status               TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'approved', 'rejected')),
    review_note          TEXT,
    reviewed_by          UUID REFERENCES auth.users(id) ON DELETE SET NULL,
    reviewed_by_email    TEXT,
    reviewed_at          TIMESTAMPTZ,
    created_at           TIMESTAMPTZ NOT NULL DEFAULT now()
);
-- Mỗi keyword duyệt chỉ có 1 outline đang sống (từ chối thì được tạo lại)
CREATE UNIQUE INDEX IF NOT EXISTS seo_outlines_keyword_active_uniq
    ON public.seo_outlines (lower(btrim(keyword))) WHERE status <> 'rejected';
CREATE INDEX IF NOT EXISTS seo_outlines_status_idx ON public.seo_outlines (status, created_at DESC);

CREATE TABLE IF NOT EXISTS public.seo_articles (
    id                 BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    outline_id         BIGINT NOT NULL REFERENCES public.seo_outlines(id) ON DELETE CASCADE,
    keyword            TEXT NOT NULL,
    title              TEXT NOT NULL,
    content_md         TEXT NOT NULL,
    meta_description   TEXT,
    seo_score          NUMERIC(5,1),
    word_count         INTEGER,
    status             TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'approved', 'rejected')),
    review_note        TEXT,
    reviewed_by        UUID REFERENCES auth.users(id) ON DELETE SET NULL,
    reviewed_by_email  TEXT,
    reviewed_at        TIMESTAMPTZ,
    created_at         TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX IF NOT EXISTS seo_articles_outline_active_uniq
    ON public.seo_articles (outline_id) WHERE status <> 'rejected';
CREATE INDEX IF NOT EXISTS seo_articles_status_idx ON public.seo_articles (status, created_at DESC);

-- Tự điền người duyệt / thời điểm duyệt khi đổi trạng thái (client không tự khai được)
CREATE OR REPLACE FUNCTION public.set_reviewer()
RETURNS TRIGGER
LANGUAGE plpgsql
SET search_path = public
AS $$
BEGIN
    IF NEW.status IS DISTINCT FROM OLD.status THEN
        IF NEW.status = 'pending' THEN
            NEW.reviewed_by := NULL; NEW.reviewed_by_email := NULL; NEW.reviewed_at := NULL;
        ELSE
            NEW.reviewed_by := auth.uid();
            NEW.reviewed_by_email := auth.jwt() ->> 'email';
            NEW.reviewed_at := now();
        END IF;
    END IF;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS seo_outlines_set_reviewer ON public.seo_outlines;
CREATE TRIGGER seo_outlines_set_reviewer BEFORE UPDATE ON public.seo_outlines
    FOR EACH ROW EXECUTE FUNCTION public.set_reviewer();
DROP TRIGGER IF EXISTS seo_articles_set_reviewer ON public.seo_articles;
CREATE TRIGGER seo_articles_set_reviewer BEFORE UPDATE ON public.seo_articles
    FOR EACH ROW EXECUTE FUNCTION public.set_reviewer();

ALTER TABLE public.seo_outlines ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.seo_articles ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "seo_outlines_select_approved" ON public.seo_outlines;
CREATE POLICY "seo_outlines_select_approved" ON public.seo_outlines
    FOR SELECT TO authenticated USING (public.is_approved());
DROP POLICY IF EXISTS "seo_outlines_update_approved" ON public.seo_outlines;
CREATE POLICY "seo_outlines_update_approved" ON public.seo_outlines
    FOR UPDATE TO authenticated USING (public.is_approved()) WITH CHECK (public.is_approved());

DROP POLICY IF EXISTS "seo_articles_select_approved" ON public.seo_articles;
CREATE POLICY "seo_articles_select_approved" ON public.seo_articles
    FOR SELECT TO authenticated USING (public.is_approved());
DROP POLICY IF EXISTS "seo_articles_update_approved" ON public.seo_articles;
CREATE POLICY "seo_articles_update_approved" ON public.seo_articles
    FOR UPDATE TO authenticated USING (public.is_approved()) WITH CHECK (public.is_approved());

-- Người dùng chỉ được sửa nội dung dàn ý / bài và trạng thái duyệt; mọi cột khác chỉ service_role ghi
REVOKE ALL ON public.seo_outlines, public.seo_articles FROM anon, authenticated;
GRANT SELECT ON public.seo_outlines, public.seo_articles TO authenticated;
GRANT UPDATE (status, review_note, outline_md) ON public.seo_outlines TO authenticated;
GRANT UPDATE (status, review_note, content_md, title, meta_description) ON public.seo_articles TO authenticated;
