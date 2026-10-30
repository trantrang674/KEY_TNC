-- Link Google Docs của bài viết (Cowork tạo file trong thư mục Drive rồi gửi kèm khi đẩy bài).
-- Dán vào Supabase > SQL Editor > Run (chạy lại nhiều lần an toàn). Chạy sau seo_content.sql.
ALTER TABLE public.seo_articles ADD COLUMN IF NOT EXISTS google_doc_url TEXT;
