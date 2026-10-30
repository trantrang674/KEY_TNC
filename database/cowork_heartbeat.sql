-- =====================================================================
-- NHỊP TIM COWORK: dashboard hiện "Cowork chạy lần cuối ..." và báo đỏ khi quá lâu không chạy
-- Dán vào Supabase > SQL Editor > Run (chạy lại nhiều lần an toàn). Chạy sau auth_postgres.sql.
-- Cowork ghi qua Edge Function cowork-api (POST /heartbeat); chỉ tài khoản approved = true mới đọc được.
-- =====================================================================

CREATE TABLE IF NOT EXISTS public.cowork_heartbeat (
    id           INT PRIMARY KEY DEFAULT 1 CHECK (id = 1),   -- chỉ một dòng duy nhất
    last_run_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    status       TEXT NOT NULL DEFAULT 'ok' CHECK (status IN ('running', 'ok', 'error')),
    summary      TEXT
);

ALTER TABLE public.cowork_heartbeat ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "cowork_heartbeat_select_approved" ON public.cowork_heartbeat;
CREATE POLICY "cowork_heartbeat_select_approved" ON public.cowork_heartbeat
    FOR SELECT TO authenticated USING (public.is_approved());

REVOKE ALL ON public.cowork_heartbeat FROM anon, authenticated;
GRANT SELECT ON public.cowork_heartbeat TO authenticated;
