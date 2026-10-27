// Nhận webhook từ Zalo Bot và lưu vào bảng public.zalo_messages.
// Triển khai: supabase functions deploy zalo-webhook --no-verify-jwt
// (Zalo không gửi khóa đăng nhập của Supabase nên không dùng withSupabase/auth; bảo vệ bằng secret token bên dưới.)
// Secret cần đặt: supabase secrets set ZALO_WEBHOOK_SECRET=<chuỗi đã dùng trong setWebhook>
// SUPABASE_URL và SUPABASE_SERVICE_ROLE_KEY được Supabase tự cấp cho Edge Function.
import "jsr:@supabase/functions-js/edge-runtime.d.ts";
import { createClient } from "jsr:@supabase/supabase-js@2";

const WEBHOOK_SECRET = Deno.env.get("ZALO_WEBHOOK_SECRET") ?? "";
const BOT_TOKEN = Deno.env.get("ZALO_BOT_TOKEN") ?? "";
const ALLOWED_CHAT_ID = Deno.env.get("ZALO_CHAT_ID") ?? "";
const GITHUB_TOKEN = Deno.env.get("GITHUB_TOKEN") ?? "";
const GITHUB_REPO = Deno.env.get("GITHUB_REPO") ?? "trantrang674/KEY_TNC";
const REPORT_URL = Deno.env.get("ZALO_REPORT_URL") ?? `https://${GITHUB_REPO.split("/")[0]}.github.io/${GITHUB_REPO.split("/")[1]}/`;
const supabase = createClient(
  Deno.env.get("SUPABASE_URL")!,
  Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!,
);

// So sánh chuỗi bí mật theo thời gian không đổi để tránh dò từng ký tự
function safeEqual(a: string, b: string): boolean {
  if (a.length !== b.length) return false;
  let diff = 0;
  for (let i = 0; i < a.length; i++) diff |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return diff === 0;
}

console.info("zalo-webhook started");

Deno.serve(async (req) => {
  if (req.method !== "POST") return new Response("Method Not Allowed", { status: 405 });

  const secret = req.headers.get("X-Bot-Api-Secret-Token") ?? "";
  if (!WEBHOOK_SECRET || !safeEqual(secret, WEBHOOK_SECRET)) {
    return new Response("Unauthorized", { status: 401 });
  }

  let payload: any;
  try {
    payload = await req.json();
  } catch {
    return new Response("Bad Request", { status: 400 });
  }

  // Payload có thể là {event_name, message} hoặc bọc trong {ok, result: {...}}
  const ev = payload?.result ?? payload;
  const msg = ev?.message ?? {};

  const { error } = await supabase.from("zalo_messages").upsert(
    {
      message_id: msg.message_id ?? null,
      event_name: ev?.event_name ?? null,
      message_type: msg.message_type ?? null,
      chat_id: msg.chat?.id ?? null,
      chat_type: msg.chat?.chat_type ?? null,
      from_id: msg.from?.id ?? null,
      display_name: msg.from?.display_name ?? null,
      is_bot: msg.from?.is_bot ?? null,
      text: msg.text ?? null,
      sent_at: typeof msg.date === "number" ? new Date(msg.date).toISOString() : null,
      raw: payload,
    },
    { onConflict: "message_id", ignoreDuplicates: true },
  );

  if (error) {
    console.error("Không lưu được tin Zalo:", error.message);
    return new Response("Server Error", { status: 500 });   // để Zalo gửi lại
  }

  // Lệnh chỉ nhận từ đúng ZALO_CHAT_ID; lỗi khi trả lời không làm Zalo gửi lại tin
  const chatId = String(msg.chat?.id ?? "");
  if (ALLOWED_CHAT_ID && chatId === ALLOWED_CHAT_ID && typeof msg.text === "string" && !msg.from?.is_bot) {
    try {
      await handleCommand(msg.text, chatId);
    } catch (e) {
      console.error("Lỗi xử lý lệnh:", (e as Error).message);
    }
  }
  return new Response("ok", { status: 200 });
});

async function sendZalo(chatId: string, text: string) {
  const res = await fetch(`https://bot-api.zaloplatforms.com/bot${BOT_TOKEN}/sendMessage`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ chat_id: chatId, text: text.slice(0, 2000) }),
  });
  if (!res.ok) console.error("sendMessage lỗi", res.status);
}

async function handleCommand(text: string, chatId: string) {
  const cmd = text.trim().split(/\s+/)[0].toLowerCase();
  if (cmd === "/top") {
    const { data } = await supabase.from("daily_reports").select("report").order("report_date", { ascending: false }).limit(1).maybeSingle();
    if (!data) return sendZalo(chatId, "Chưa có báo cáo nào.");
    return sendZalo(chatId, `💥 Helu, em vừa quét xong website Keyword_Ngành xong lúc ${data.report?.generated_at ?? ""}\n👉 Chị vào xem báo cáo trong link này: ${REPORT_URL}`);
  }
  if (cmd === "/quet") {
    if (!GITHUB_TOKEN) return sendZalo(chatId, "Chưa cấu hình GITHUB_TOKEN nên chưa gọi quét được.");
    const res = await fetch(`https://api.github.com/repos/${GITHUB_REPO}/actions/workflows/daily-pages.yml/dispatches`, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${GITHUB_TOKEN}`,
        Accept: "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "zalo-webhook",
      },
      body: JSON.stringify({ ref: "main", inputs: { ui_only: "false" } }),
    });
    return sendZalo(chatId, res.status === 204
      ? "Đã gọi quét. Xong sẽ báo kết quả tại đây (khoảng vài phút)."
      : `Không gọi được quét (GitHub trả ${res.status}).`);
  }
  return sendZalo(chatId, "Lệnh hỗ trợ:\n/quet — quét lại và báo Top keyword\n/top — xem báo cáo gần nhất");
}
