// API cho Cowork (Claude) lấy keyword đã duyệt và đẩy outline / bài viết lên Supabase.
// Triển khai: supabase functions deploy cowork-api --no-verify-jwt
// Secret cần đặt: supabase secrets set COWORK_API_KEY=<chuỗi bí mật dài, ngẫu nhiên>
// SUPABASE_URL và SUPABASE_SERVICE_ROLE_KEY được Supabase tự cấp cho Edge Function.
//
// Mọi request phải có header:  x-api-key: <COWORK_API_KEY>
//   GET  /cowork-api/keywords           keyword đã duyệt CHƯA có outline (?all=1 để lấy tất cả)
//   POST /cowork-api/outlines           đẩy outline (status = pending)
//   GET  /cowork-api/outlines/approved  outline đã được duyệt và CHƯA có bài viết
//   POST /cowork-api/articles           đẩy bài viết (status = pending)
//   POST /cowork-api/notifications      báo tin lên chuông dashboard {level, title, message, keyword}
//   POST /cowork-api/heartbeat          báo "Cowork vừa chạy" {status: running|ok|error, summary}
//   GET  /cowork-api/refresh-candidates bài nên làm mới (clicks / hiển thị giảm hoặc tụt hạng), tối đa 10 bài
//   (GET /keywords trả thêm rejected_note, GET /outlines/approved trả thêm rejected_article_note: lý do người duyệt từ chối bản trước)
import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

const API_KEY = Deno.env.get("COWORK_API_KEY") ?? "";
const supabase = createClient(
  Deno.env.get("SUPABASE_URL")!,
  Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!,
);

const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json; charset=utf-8" } });

// So sánh thời gian không đổi để không lộ khóa qua độ trễ
function sameKey(a: string, b: string): boolean {
  if (!b || a.length !== b.length) return false;
  let diff = 0;
  for (let i = 0; i < a.length; i++) diff |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return diff === 0;
}

const str = (v: unknown, max: number) => (typeof v === "string" ? v.trim().slice(0, max) : "");
const strList = (v: unknown) => (Array.isArray(v) ? v.map((x) => str(x, 200)).filter(Boolean).slice(0, 20) : []);

Deno.serve(async (req) => {
  if (!sameKey(req.headers.get("x-api-key") ?? "", API_KEY)) return json({ error: "unauthorized" }, 401);

  const url = new URL(req.url);
  const route = url.pathname.replace(/^.*\/cowork-api/, "").replace(/\/+$/, "") || "/";

  try {
    if (req.method === "GET" && route === "/keywords") {
      const { data: kws, error } = await supabase.from("approved_keywords")
        .select("id, keyword, source_keyword, niche, intent, based_on, report_date, approved_at")
        .order("approved_at", { ascending: true });
      if (error) throw error;
      if (url.searchParams.get("all") === "1") return json({ keywords: kws });
      const { data: outs, error: e2 } = await supabase.from("seo_outlines").select("keyword, status").neq("status", "rejected");
      if (e2) throw e2;
      const done = new Set((outs ?? []).map((o) => o.keyword.trim().toLowerCase()));
      // Outline bị từ chối gần nhất của mỗi keyword: Cowork đọc rejected_note để lập lại đúng chỗ người duyệt chê
      const { data: rej, error: e3 } = await supabase.from("seo_outlines")
        .select("keyword, review_note, reviewed_at").eq("status", "rejected").order("reviewed_at", { ascending: true });
      if (e3) throw e3;
      const lastRej = new Map<string, string>();
      for (const r of rej ?? []) if (r.review_note) lastRej.set(r.keyword.trim().toLowerCase(), r.review_note);
      return json({
        keywords: (kws ?? []).filter((k) => !done.has(k.keyword.trim().toLowerCase()))
          .map((k) => ({ ...k, rejected_note: lastRej.get(k.keyword.trim().toLowerCase()) ?? null })),
      });
    }

    if (req.method === "POST" && route === "/outlines") {
      const b = await req.json();
      const keyword = str(b.keyword, 300);
      const outline_md = str(b.outline_md, 60000);
      if (!keyword || !outline_md) return json({ error: "keyword và outline_md là bắt buộc" }, 400);
      const { data, error } = await supabase.from("seo_outlines").insert({
        approved_keyword_id: Number.isInteger(b.approved_keyword_id) ? b.approved_keyword_id : null,
        keyword,
        outline_md,
        short_kws: strList(b.short_kws),
        long_kws: strList(b.long_kws),
        research: b.research && JSON.stringify(b.research).length <= 500000 ? b.research : null,
        status: "pending", // luôn chờ duyệt, client không chọn được
      }).select("id, keyword, status").single();
      if (error) return json({ error: error.message }, error.code === "23505" ? 409 : 500);
      return json({ outline: data }, 201);
    }

    if (req.method === "GET" && route === "/outlines/approved") {
      const { data: outs, error } = await supabase.from("seo_outlines")
        .select("id, keyword, outline_md, short_kws, long_kws, research, reviewed_at, review_note")
        .eq("status", "approved").order("reviewed_at", { ascending: true });
      if (error) throw error;
      const { data: arts, error: e2 } = await supabase.from("seo_articles").select("outline_id").neq("status", "rejected");
      if (e2) throw e2;
      const written = new Set((arts ?? []).map((a) => a.outline_id));
      // Bài bị từ chối gần nhất của outline: Cowork đọc rejected_article_note để viết lại đúng chỗ bị chê
      const { data: rejArts, error: e3 } = await supabase.from("seo_articles")
        .select("outline_id, review_note, reviewed_at").eq("status", "rejected").order("reviewed_at", { ascending: true });
      if (e3) throw e3;
      const lastRej = new Map<number, string>();
      for (const a of rejArts ?? []) if (a.review_note) lastRej.set(a.outline_id, a.review_note);
      return json({
        outlines: (outs ?? []).filter((o) => !written.has(o.id)).map((o) => ({ ...o, rejected_article_note: lastRej.get(o.id) ?? null })),
      });
    }

    // Bài nên làm mới: clicks / hiển thị giảm hoặc tụt hạng (14 ngày gần nhất so với 14 ngày trước, bỏ ngày cuối).
    // Ngưỡng phải khớp với ACT trong frontend/index.html (tab BÁO CÁO > Bài cần xử lý).
    if (req.method === "GET" && route === "/refresh-candidates") {
      const { data: rows, error } = await supabase.from("seo_article_metrics")
        .select("url, title, is_dashboard, article_id, published_date, daily, data_end_date");
      if (error) throw error;
      const ends = (rows ?? []).map((r) => r.data_end_date).filter(Boolean).sort();
      const endStr = ends[ends.length - 1];
      if (!endStr) return json({ candidates: [], note: "chưa có số liệu GSC" });
      const day = 86400000;
      const end = new Date(endStr + "T00:00:00Z").getTime();
      const iso = (ms: number) => new Date(ms).toISOString().slice(0, 10);
      const curTo = iso(end - 1 * day), curFrom = iso(end - 14 * day);
      const prevTo = iso(end - 15 * day), prevFrom = iso(end - 28 * day);
      const sum = (daily: { d: string; c: number; i: number; p: number }[], from: string, to: string) => {
        let c = 0, i = 0, pw = 0;
        for (const r of daily) if (r.d >= from && r.d <= to) { c += r.c; i += r.i; pw += r.p * r.i; }
        return { clicks: c, impr: i, pos: i ? pw / i : 0 };
      };
      const found: Record<string, unknown>[] = [];
      for (const r of rows ?? []) {
        const daily = Array.isArray(r.daily) ? r.daily : [];
        if (!daily.length) continue;
        const cur = sum(daily, curFrom, curTo), prev = sum(daily, prevFrom, prevTo);
        const reasons: string[] = [];
        if (prev.clicks >= 10 && cur.clicks <= prev.clicks * 0.7) {
          reasons.push(`Clicks giảm ${Math.round(((prev.clicks - cur.clicks) / prev.clicks) * 100)}% (${prev.clicks} → ${cur.clicks})`);
        } else if (prev.impr >= 300 && cur.impr <= prev.impr * 0.6) {
          reasons.push(`Lượt hiển thị giảm ${Math.round(((prev.impr - cur.impr) / prev.impr) * 100)}% (${prev.impr} → ${cur.impr})`);
        }
        if (cur.impr >= 100 && prev.impr >= 100 && Math.round(cur.pos) - Math.round(prev.pos) >= 3) {
          reasons.push(`Tụt hạng từ #${Math.round(prev.pos)} xuống #${Math.round(cur.pos)}`);
        }
        if (!reasons.length) continue;
        found.push({
          url: r.url, title: r.title, is_dashboard: r.is_dashboard, article_id: r.article_id, published_date: r.published_date,
          reasons, clicks_recent: cur.clicks, clicks_previous: prev.clicks, position_recent: Math.round(cur.pos),
          position_previous: Math.round(prev.pos), lost: prev.clicks - cur.clicks,
        });
      }
      // Bài của Cowork dashboard xếp trước, trong mỗi nhóm bài mất nhiều click nhất lên đầu
      found.sort((a, b) => (Number(!!b.is_dashboard) - Number(!!a.is_dashboard)) || ((b.lost as number) - (a.lost as number)));
      const top = found.slice(0, 10);
      // Gắn keyword gốc cho bài của dashboard để Cowork biết bài viết về từ khóa nào
      const ids = top.map((t) => t.article_id).filter((v) => Number.isInteger(v));
      const kwById = new Map<number, string>();
      if (ids.length) {
        const { data: arts } = await supabase.from("seo_articles").select("id, keyword").in("id", ids as number[]);
        for (const a of arts ?? []) kwById.set(a.id, a.keyword);
      }
      return json({ data_end_date: endStr, candidates: top.map((t) => ({ ...t, keyword: kwById.get(t.article_id as number) ?? null })) });
    }

    if (req.method === "POST" && route === "/heartbeat") {
      const b = await req.json().catch(() => ({}));
      const status = ["running", "ok", "error"].includes(b.status) ? b.status : "ok";
      const { error } = await supabase.from("cowork_heartbeat").upsert({
        id: 1, last_run_at: new Date().toISOString(), status, summary: str(b.summary, 500) || null,
      });
      if (error) throw error;
      return json({ ok: true });
    }

    if (req.method === "POST" && route === "/articles") {
      const b = await req.json();
      const content_md = str(b.content_md, 200000);
      const title = str(b.title, 300);
      if (!Number.isInteger(b.outline_id) || !title || !content_md) {
        return json({ error: "outline_id, title, content_md là bắt buộc" }, 400);
      }
      const { data: outline, error: e1 } = await supabase.from("seo_outlines")
        .select("id, keyword, status").eq("id", b.outline_id).maybeSingle();
      if (e1) throw e1;
      if (!outline) return json({ error: "không có outline này" }, 404);
      if (outline.status !== "approved") return json({ error: "outline chưa được duyệt, không được viết bài" }, 409);
      const { data, error } = await supabase.from("seo_articles").insert({
        outline_id: outline.id,
        keyword: outline.keyword,
        title,
        content_md,
        meta_description: str(b.meta_description, 400) || null,
        seo_score: typeof b.seo_score === "number" && b.seo_score >= 0 && b.seo_score <= 100 ? b.seo_score : null,
        word_count: Number.isInteger(b.word_count) ? b.word_count : null,
        // Chỉ nhận link Google Docs/Drive, bỏ qua mọi URL khác
        google_doc_url: /^https:\/\/(docs|drive)\.google\.com\//.test(str(b.google_doc_url, 500)) ? str(b.google_doc_url, 500) : null,
        status: "pending",
      }).select("id, keyword, status").single();
      if (error) return json({ error: error.message }, error.code === "23505" ? 409 : 500);
      return json({ article: data }, 201);
    }

    if (req.method === "POST" && route === "/notifications") {
      const b = await req.json();
      const title = str(b.title, 200);
      if (!title) return json({ error: "title là bắt buộc" }, 400);
      const level = ["info", "success", "warning", "error"].includes(b.level) ? b.level : "info";
      const { data, error } = await supabase.from("cowork_notifications").insert({
        level,
        title,
        message: str(b.message, 2000) || null,
        keyword: str(b.keyword, 300) || null,
      }).select("id, level, title").single();
      if (error) throw error;
      return json({ notification: data }, 201);
    }

    return json({ error: "not found" }, 404);
  } catch (err) {
    console.error(err);
    return json({ error: (err as Error).message ?? "lỗi máy chủ" }, 500);
  }
});
