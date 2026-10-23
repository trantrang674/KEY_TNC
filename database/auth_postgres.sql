-- =====================================================================
-- ĐĂNG NHẬP BẢO MẬT cho dashboard (Supabase Auth + RLS)
-- Cách dùng: dán toàn bộ vào Supabase > SQL Editor > Run (chạy lại nhiều lần an toàn).
-- Cơ chế:
--   * Chế độ CHỈ-ADMIN-TẠO-TÀI-KHOẢN: tài khoản mới mặc định approved = TRUE, nên BẮT BUỘC tắt
--     "Allow new users to sign up" trong Supabase Dashboard (xem database/admin_only_users.sql).
--     Muốn chế độ "đăng ký tự do + chờ duyệt" thì đổi DEFAULT của cột approved thành FALSE.
--   * Chỉ tài khoản approved = true mới đọc được báo cáo (daily_reports).
--   * Người dùng KHÔNG tự duyệt được mình (không có policy UPDATE trên profiles).
--   * Việc ghi báo cáo do GitHub Actions làm bằng service_role key (bỏ qua RLS).
-- =====================================================================

-- 1. Hồ sơ người dùng + cờ duyệt
CREATE TABLE IF NOT EXISTS public.profiles (
    id          UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    email       TEXT,
    approved    BOOLEAN NOT NULL DEFAULT TRUE,    -- chế độ chỉ-admin-tạo-tài-khoản: PHẢI tắt "Allow new users to sign up" trong Dashboard
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
ALTER TABLE public.profiles ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "profiles_select_own" ON public.profiles;
CREATE POLICY "profiles_select_own" ON public.profiles
    FOR SELECT TO authenticated
    USING (id = (SELECT auth.uid()));

-- 2. Tự tạo hồ sơ khi có người đăng ký
CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
BEGIN
    INSERT INTO public.profiles (id, email) VALUES (NEW.id, NEW.email)
    ON CONFLICT (id) DO NOTHING;
    RETURN NEW;
END;
$$;
REVOKE EXECUTE ON FUNCTION public.handle_new_user() FROM PUBLIC, anon, authenticated;

DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;
CREATE TRIGGER on_auth_user_created
    AFTER INSERT ON auth.users
    FOR EACH ROW EXECUTE FUNCTION public.handle_new_user();

-- Tạo hồ sơ cho các tài khoản đã tồn tại từ trước (nếu có)
INSERT INTO public.profiles (id, email)
SELECT id, email FROM auth.users
ON CONFLICT (id) DO NOTHING;

-- 3. Hàm kiểm tra "đã được duyệt" dùng trong policy
CREATE OR REPLACE FUNCTION public.is_approved()
RETURNS BOOLEAN
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = public
AS $$
    SELECT EXISTS (
        SELECT 1 FROM public.profiles
        WHERE id = (SELECT auth.uid()) AND approved
    );
$$;
REVOKE EXECUTE ON FUNCTION public.is_approved() FROM PUBLIC, anon;
GRANT  EXECUTE ON FUNCTION public.is_approved() TO authenticated;

-- 4. Báo cáo hằng ngày (mỗi ngày 1 dòng, cả báo cáo lưu dạng JSON)
CREATE TABLE IF NOT EXISTS public.daily_reports (
    report_date  DATE PRIMARY KEY,
    report       JSONB NOT NULL,
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);
ALTER TABLE public.daily_reports ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "daily_reports_select_approved" ON public.daily_reports;
CREATE POLICY "daily_reports_select_approved" ON public.daily_reports
    FOR SELECT TO authenticated
    USING (public.is_approved());

-- =====================================================================
-- CÁCH DUYỆT NGƯỜI DÙNG (chạy trong SQL Editor, hoặc bật cột approved trong Table Editor > profiles):
--   UPDATE public.profiles SET approved = TRUE  WHERE email = 'ten@congty.com';
-- Thu hồi quyền:
--   UPDATE public.profiles SET approved = FALSE WHERE email = 'ten@congty.com';
-- Xem ai đang chờ duyệt:
--   SELECT email, created_at FROM public.profiles WHERE NOT approved ORDER BY created_at DESC;
-- =====================================================================
