// Báo qua Zalo Bot khi có: keyword mới được duyệt, outline chờ duyệt, bài viết chờ duyệt.
// Được gọi bởi trigger Postgres (database/zalo_notify.sql) qua pg_net mỗi khi có dòng mới.
// Triển khai: supabase functions deploy zalo-notify --no-verify-jwt
// (pg_net không có khóa đăng nhập của Supabase nên bảo vệ bằng secret token bên dưới.)
// Secret cần đặt:
//   supabase secrets set ZALO_NOTIFY_SECRET=<chuỗi ngẫu nhiên dài, trùng với Vault zalo_notify_secret>
//   supabase secrets set ZALO_BOT_TOKEN=... ZALO_CHAT_ID=...   (đã có nếu đã triển khai zalo-webhook)
// Tùy chọn: ZALO_REPORT_URL (mặc định dựng từ GITHUB_REPO như zalo-webhook)

const NOTIFY_SECRET = Deno.env.get("ZALO_NOTIFY_SECRET") ?? "";
const BOT_TOKEN = Deno.env.get("ZALO_BOT_TOKEN") ?? "";
const CHAT_ID = Deno.env.get("ZALO_CHAT_ID") ?? "";
const GITHUB_REPO = Deno.env.get("GITHUB_REPO") ?? "trantrang674/KEY_TNC";
const REPORT_URL = Deno.env.get("ZALO_REPORT_URL") ?? `https://${GITHUB_REPO.split("/")[0]}.github.io/${GITHUB_REPO.split("/")[1]}/`;

// So sánh chuỗi bí mật theo thời gian không đổi để tránh dò từng ký tự
function safeEqual(a: string, b: string): boolean {
  if (!b || a.length !== b.length) return false;
  let diff = 0;
  for (let i = 0; i < a.length; i++) diff |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return diff === 0;
}

const clip = (v: unknown, max: number) => String(v ?? "").trim().slice(0, max);

function buildMessage(table: string, r: Record<string, unknown>): string | null {
  const link = `👉 Chị vào duyệt tại: ${REPORT_URL}`;
  if (table === "approved_keywords") {
    const who = r.approved_by_email ? ` (duyệt bởi ${clip(r.approved_by_email, 80)})` : "";
    return `📥 Em đã nhận keyword mới: “${clip(r.keyword, 200)}”${who}\nEm sẽ lập outline ở lượt chạy tới của Cowork.`;
  }
  if (table === "seo_outlines") {
    return `📝 Em đã lên xong outline cho keyword “${clip(r.keyword, 200)}”, đang chờ chị duyệt.\n${link}`;
  }
  if (table === "seo_articles") {
    const score = r.seo_score != null ? ` | SEO ${r.seo_score}` : "";
    const words = r.word_count != null ? ` | ${r.word_count} từ` : "";
    return `✅ Em đã viết xong bài “${clip(r.title, 200)}” (keyword: ${clip(r.keyword, 120)}${score}${words}), đang chờ chị duyệt.\n${link}`;
  }
  return null;
}

console.info("zalo-notify started");

Deno.serve(async (req) => {
  if (req.method !== "POST") return new Response("Method Not Allowed", { status: 405 });
  if (!safeEqual(req.headers.get("x-notify-secret") ?? "", NOTIFY_SECRET)) {
    return new Response("Unauthorized", { status: 401 });
  }
  if (!BOT_TOKEN || !CHAT_ID) return new Response("Zalo chưa cấu hình", { status: 500 });

  let body: { table?: string; record?: Record<string, unknown> };
  try {
    body = await req.json();
  } catch {
    return new Response("Bad Request", { status: 400 });
  }

  const text = buildMessage(String(body.table ?? ""), body.record ?? {});
  if (!text) return new Response("ignored", { status: 200 });

  const res = await fetch(`https://bot-api.zaloplatforms.com/bot${BOT_TOKEN}/sendMessage`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ chat_id: CHAT_ID, text: text.slice(0, 2000) }),
  });
  if (!res.ok) {
    console.error("Zalo sendMessage lỗi", res.status);
    return new Response("Zalo error", { status: 502 });
  }
  return new Response("ok", { status: 200 });
});
