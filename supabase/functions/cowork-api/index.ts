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
      return json({ keywords: (kws ?? []).filter((k) => !done.has(k.keyword.trim().toLowerCase())) });
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
      return json({ outlines: (outs ?? []).filter((o) => !written.has(o.id)) });
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
        status: "pending",
      }).select("id, keyword, status").single();
      if (error) return json({ error: error.message }, error.code === "23505" ? 409 : 500);
      return json({ article: data }, 201);
    }

    return json({ error: "not found" }, 404);
  } catch (err) {
    console.error(err);
    return json({ error: (err as Error).message ?? "lỗi máy chủ" }, 500);
  }
});
