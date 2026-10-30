-- =====================================================================
-- THÔNG BÁO TỪ COWORK hiện ở chuông trên header dashboard
-- Cách dùng: chạy auth_postgres.sql trước, sau đó dán file này vào Supabase > SQL Editor > Run (chạy lại nhiều lần an toàn).
-- Cơ chế:
--   * Cowork ghi qua Edge Function cowork-api (POST /notifications, service_role), không ghi trực tiếp.
--   * Chỉ tài khoản approved = true mới đọc được. Trạng thái "đã đọc" lưu trong trình duyệt của từng người.
-- =====================================================================

CREATE TABLE IF NOT EXISTS public.cowork_notifications (
    id          BIGSERIAL PRIMARY KEY,
    level       TEXT NOT NULL DEFAULT 'info' CHECK (level IN ('info', 'success', 'warning', 'error')),
    title       TEXT NOT NULL,
    message     TEXT,
    keyword     TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS cowork_notifications_created_idx ON public.cowork_notifications (created_at DESC);

ALTER TABLE public.cowork_notifications ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "cowork_notifications_select_approved" ON public.cowork_notifications;
CREATE POLICY "cowork_notifications_select_approved" ON public.cowork_notifications
    FOR SELECT TO authenticated USING (public.is_approved());

REVOKE ALL ON public.cowork_notifications FROM anon, authenticated;
GRANT SELECT ON public.cowork_notifications TO authenticated;
