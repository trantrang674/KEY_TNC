-- =====================================================================
-- BÁO ZALO khi: có keyword mới được duyệt / có outline chờ duyệt / có bài viết chờ duyệt
-- Cách dùng:
--   1. Chạy approved_keywords.sql và seo_content.sql trước.
--   2. Triển khai Edge Function:  supabase functions deploy zalo-notify --no-verify-jwt
--      và đặt secret:             supabase secrets set ZALO_NOTIFY_SECRET=<chuoi-ngau-nhien-dai>
--   3. Lưu 2 giá trị vào Vault (SQL Editor, chạy 1 lần, thay giá trị thật; KHÔNG commit giá trị thật):
--        select vault.create_secret('https://<project-ref>.supabase.co/functions/v1/zalo-notify', 'zalo_notify_url');
--        select vault.create_secret('<đúng chuỗi ZALO_NOTIFY_SECRET ở bước 2>', 'zalo_notify_secret');
--   4. Dán file này vào SQL Editor > Run (chạy lại nhiều lần an toàn).
-- Cơ chế: trigger AFTER INSERT gọi Edge Function qua pg_net (bất đồng bộ). Lỗi gửi tin KHÔNG làm hỏng việc ghi dữ liệu.
-- =====================================================================

CREATE EXTENSION IF NOT EXISTS pg_net WITH SCHEMA extensions;

CREATE OR REPLACE FUNCTION public.notify_zalo()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, extensions
AS $$
DECLARE
    v_url    TEXT;
    v_secret TEXT;
BEGIN
    SELECT decrypted_secret INTO v_url    FROM vault.decrypted_secrets WHERE name = 'zalo_notify_url'    LIMIT 1;
    SELECT decrypted_secret INTO v_secret FROM vault.decrypted_secrets WHERE name = 'zalo_notify_secret' LIMIT 1;
    IF v_url IS NULL OR v_secret IS NULL THEN
        RETURN NEW;   -- chưa cấu hình Vault thì bỏ qua êm
    END IF;

    PERFORM net.http_post(
        url     := v_url,
        headers := jsonb_build_object('Content-Type', 'application/json', 'x-notify-secret', v_secret),
        body    := jsonb_build_object('table', TG_TABLE_NAME, 'record', to_jsonb(NEW) - 'research' - 'outline_md' - 'content_md')
    );
    RETURN NEW;
EXCEPTION WHEN OTHERS THEN
    RAISE WARNING 'notify_zalo lỗi: %', SQLERRM;   -- không chặn việc ghi dữ liệu
    RETURN NEW;
END;
$$;

-- Chỉ trigger/hệ thống gọi hàm này, không cho client gọi trực tiếp
REVOKE ALL ON FUNCTION public.notify_zalo() FROM PUBLIC, anon, authenticated;

DROP TRIGGER IF EXISTS approved_keywords_notify_zalo ON public.approved_keywords;
CREATE TRIGGER approved_keywords_notify_zalo AFTER INSERT ON public.approved_keywords
    FOR EACH ROW EXECUTE FUNCTION public.notify_zalo();

DROP TRIGGER IF EXISTS seo_outlines_notify_zalo ON public.seo_outlines;
CREATE TRIGGER seo_outlines_notify_zalo AFTER INSERT ON public.seo_outlines
    FOR EACH ROW EXECUTE FUNCTION public.notify_zalo();

DROP TRIGGER IF EXISTS seo_articles_notify_zalo ON public.seo_articles;
CREATE TRIGGER seo_articles_notify_zalo AFTER INSERT ON public.seo_articles
    FOR EACH ROW EXECUTE FUNCTION public.notify_zalo();
