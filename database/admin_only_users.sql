-- =====================================================================
-- CHẾ ĐỘ "CHỈ QUẢN TRỊ VIÊN TẠO TÀI KHOẢN"
-- Chạy 1 lần trong Supabase > SQL Editor. Chạy lại an toàn.
--
-- QUAN TRỌNG: file này chỉ làm tài khoản do bạn tạo TỰ ĐƯỢC XEM báo cáo.
-- Việc CHẶN người lạ tự đăng ký phải làm bằng công tắc trong Dashboard:
--   Authentication > Sign In / Providers > tắt "Allow new users to sign up".
-- (Nếu công tắc đó còn bật thì bất kỳ ai gọi API đăng ký đều có tài khoản xem được báo cáo!)
-- =====================================================================

-- 1. Tài khoản mới (do admin tạo) mặc định được duyệt
ALTER TABLE public.profiles ALTER COLUMN approved SET DEFAULT TRUE;

-- 2. Xem lại toàn bộ tài khoản hiện có để rà soát người lạ (nếu có, xóa trong Authentication > Users)
SELECT p.email, p.approved, p.created_at
FROM public.profiles p
ORDER BY p.created_at;

-- Thu hồi quyền xem của một người (không xóa tài khoản):
--   UPDATE public.profiles SET approved = FALSE WHERE email = 'ten@congty.com';
-- Cấp lại:
--   UPDATE public.profiles SET approved = TRUE  WHERE email = 'ten@congty.com';
