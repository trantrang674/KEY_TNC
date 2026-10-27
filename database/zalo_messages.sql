-- Tin nhắn nhận từ Zalo Bot qua webhook (Edge Function zalo-webhook ghi bằng service_role).
-- Chạy trong Supabase: SQL Editor -> dán toàn bộ -> Run. Chạy lại nhiều lần vẫn an toàn.

CREATE TABLE IF NOT EXISTS public.zalo_messages (
    id            BIGSERIAL PRIMARY KEY,
    message_id    TEXT UNIQUE,              -- id tin nhắn của Zalo (chống ghi trùng khi Zalo gửi lại)
    event_name    TEXT,                     -- vd: message.text.received
    message_type  TEXT,                     -- vd: CHAT_TEXT
    chat_id       TEXT,
    chat_type     TEXT,                     -- vd: PRIVATE
    from_id       TEXT,
    display_name  TEXT,
    is_bot        BOOLEAN,
    text          TEXT,
    sent_at       TIMESTAMPTZ,              -- thời điểm gửi theo Zalo (message.date, mili giây)
    raw           JSONB NOT NULL,           -- toàn bộ payload gốc, để không mất dữ liệu loại tin khác (ảnh, sticker...)
    received_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Bảng đã tạo từ phiên bản cũ thì bổ sung các cột mới
ALTER TABLE public.zalo_messages ADD COLUMN IF NOT EXISTS message_type TEXT;
ALTER TABLE public.zalo_messages ADD COLUMN IF NOT EXISTS chat_type TEXT;
ALTER TABLE public.zalo_messages ADD COLUMN IF NOT EXISTS is_bot BOOLEAN;
ALTER TABLE public.zalo_messages ADD COLUMN IF NOT EXISTS sent_at TIMESTAMPTZ;

CREATE INDEX IF NOT EXISTS zalo_messages_chat_idx ON public.zalo_messages (chat_id, received_at DESC);

-- Bật RLS và KHÔNG tạo policy nào: chỉ service_role (Edge Function) đọc/ghi được, trình duyệt thì không.
ALTER TABLE public.zalo_messages ENABLE ROW LEVEL SECURITY;
