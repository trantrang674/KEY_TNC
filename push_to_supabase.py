# -*- coding: utf-8 -*-
"""Đẩy dữ liệu từ data/tnc.db (SQLite) lên Supabase qua REST API.
Cần trong .env: SUPABASE_URL, SUPABASE_SERVICE_KEY. Chạy: python push_to_supabase.py
Chạy lại nhiều lần an toàn: dùng upsert theo khóa tự nhiên, id mới do Supabase cấp và được ánh xạ lại.
"""
import json
import os
import sqlite3
import sys
from pathlib import Path
from urllib.parse import quote

import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / ".env")
URL = os.getenv("SUPABASE_URL", "").rstrip("/")
KEY = os.getenv("SUPABASE_SERVICE_KEY", "").strip()
if not URL or not KEY:
    sys.exit("Thiếu SUPABASE_URL / SUPABASE_SERVICE_KEY trong .env")

HEADERS = {"apikey": KEY, "Authorization": f"Bearer {KEY}", "Content-Type": "application/json"}
db = sqlite3.connect(ROOT / "data" / "tnc.db")
db.row_factory = sqlite3.Row


def rows(sql, *p):
    return [dict(r) for r in db.execute(sql, p).fetchall()]


def post(table, data, on_conflict=None, ignore=False, ret=False):
    """POST theo lô. Trả về các dòng Supabase trả lại nếu ret=True."""
    out = []
    for i in range(0, len(data), 200):
        batch = data[i:i + 200]
        prefer = []
        if on_conflict:
            prefer.append("resolution=ignore-duplicates" if ignore else "resolution=merge-duplicates")
        prefer.append("return=representation" if ret else "return=minimal")
        q = f"?on_conflict={on_conflict}" if on_conflict else ""
        r = requests.post(f"{URL}/rest/v1/{table}{q}", headers={**HEADERS, "Prefer": ",".join(prefer)},
                          data=json.dumps(batch, ensure_ascii=False).encode("utf-8"), timeout=60)
        if r.status_code >= 300:
            sys.exit(f"[{table}] lỗi {r.status_code}: {r.text[:400]}")
        if ret:
            out.extend(r.json())
    print(f"  {table}: {len(data)} dòng")
    return out


def delete(table, query):
    r = requests.delete(f"{URL}/rest/v1/{table}?{query}", headers={**HEADERS, "Prefer": "return=minimal"}, timeout=30)
    if r.status_code >= 300:
        sys.exit(f"[delete {table}] lỗi {r.status_code}: {r.text[:300]}")


def get(table, query):
    r = requests.get(f"{URL}/rest/v1/{table}?{query}", headers=HEADERS, timeout=30)
    r.raise_for_status()
    return r.json()


def b(v):
    return bool(v)


# 1. Niches
print("Đang đẩy dữ liệu...")
post("niches", rows("SELECT id, name, badge_color, group_name FROM niches"), "id")

# 2. Sources
src_rows = rows("SELECT * FROM sources")
res = post("sources", [{"name": s["name"], "source_type": s["source_type"], "badge": s["badge"],
                        "domain": s["domain"], "feed_url": s["feed_url"], "is_active": b(s["is_active"])}
                       for s in src_rows], "name", ret=True)
src_map = {s["id"]: next(x["id"] for x in res if x["name"] == s["name"]) for s in src_rows}

# 3. SerpApi: runs -> calls -> children (xóa calls cũ của các run này để chạy lại không nhân đôi)
run_rows = rows("SELECT * FROM serpapi_runs")
res = post("serpapi_runs", [{"run_date": r["run_date"], "executed_at": r["executed_at"], "forced": b(r["forced"])}
                            for r in run_rows], "run_date", ret=True)
run_map = {r["id"]: next(x["id"] for x in res if x["run_date"] == r["run_date"]) for r in run_rows}
for new_id in run_map.values():
    delete("serpapi_calls", f"serpapi_run=eq.{new_id}")

call_rows = rows("SELECT * FROM serpapi_calls")
res = post("serpapi_calls", [{
    "serpapi_run": run_map[c["serpapi_run"]], "engine": c["engine"], "query": c["query"], "status": c["status"],
    "result_count": c["result_count"], "error_message": c["error_message"],
    "raw_json": json.loads(c["raw_json"]) if c["raw_json"] else None} for c in call_rows],
    "serpapi_run,engine", ret=True)
call_map = {c["id"]: next(x["id"] for x in res if x["serpapi_run"] == run_map[c["serpapi_run"]]
                          and x["engine"] == c["engine"]) for c in call_rows}

tq_rows = rows("SELECT * FROM trending_queries ORDER BY id")
res = post("trending_queries", [{
    "call_id": call_map[t["call_id"]], "query": t["query"], "search_volume": t["search_volume"],
    "increase_percentage": t["increase_percentage"],
    "categories": json.loads(t["categories"]) if t["categories"] else None} for t in tq_rows], ret=True)
assert len(res) == len(tq_rows) and all(x["query"] == t["query"] for x, t in zip(res, tq_rows)), "lệch thứ tự trending_queries"
tq_map = {t["id"]: x["id"] for t, x in zip(tq_rows, res)}

post("trending_related_queries",
     [{"trending_id": tq_map[r["trending_id"]], "related": r["related"]}
      for r in rows("SELECT * FROM trending_related_queries")], "trending_id,related", ignore=True)
post("autocomplete_suggestions",
     [{"call_id": call_map[a["call_id"]], "seed": a["seed"], "suggestion": a["suggestion"]}
      for a in rows("SELECT * FROM autocomplete_suggestions")])
post("google_trends_scores",
     [{"call_id": call_map[g["call_id"]], "query": g["query"], "score": g["score"]}
      for g in rows("SELECT * FROM google_trends_scores")], "call_id,query")

quota = rows("SELECT * FROM serpapi_quota_snapshots")
for q in quota:
    if not get("serpapi_quota_snapshots", f"captured_at=eq.{quote(q['captured_at'])}&select=id"):
        post("serpapi_quota_snapshots", [{k: q[k] for k in ("captured_at", "plan_name", "searches_left",
                                                            "searches_per_month", "this_month_usage")}])

# 4. Keywords & Articles
kw_rows = rows("SELECT * FROM keywords")
res = post("keywords", [{"cluster_id": k["cluster_id"], "display_keyword": k["display_keyword"],
                         "niche_id": k["niche_id"], "first_seen_at": k["first_seen_at"],
                         "last_seen_at": k["last_seen_at"]} for k in kw_rows], "cluster_id", ret=True)
kw_map = {k["id"]: next(x["id"] for x in res if x["cluster_id"] == k["cluster_id"]) for k in kw_rows}

art_rows = rows("SELECT * FROM articles")
res = post("articles", [{
    "source_id": src_map[a["source_id"]], "url": a["url"], "title": a["title"],
    "title_norm_hash": a["title_norm_hash"], "summary": a["summary"], "published_at": a["published_at"],
    "fetched_at": a["fetched_at"], "origin": a["origin"], "niche_id": a["niche_id"],
    "niche_relevance": a["niche_relevance"], "is_noise": b(a["is_noise"]), "noise_reason": a["noise_reason"]}
    for a in art_rows], "url", ret=True)
art_map = {a["id"]: next(x["id"] for x in res if x["url"] == a["url"]) for a in art_rows}

post("article_keywords", [{"article_id": art_map[x["article_id"]], "keyword_id": kw_map[x["keyword_id"]]}
                          for x in rows("SELECT * FROM article_keywords")], "article_id,keyword_id", ignore=True)

# 5. Báo cáo: report_runs -> rankings -> ranking_articles / seo_suggestions
rr_map = {}
for r in rows("SELECT * FROM report_runs"):
    found = get("report_runs", f"generated_at=eq.{quote(r['generated_at'])}&select=id")
    if found:
        rr_map[r["id"]] = found[0]["id"]
        continue
    res = post("report_runs", [{
        "generated_at": r["generated_at"], "time_window_hours": r["time_window_hours"],
        "total_articles_scanned": r["total_articles_scanned"], "total_clusters": r["total_clusters"],
        "serpapi_run_id": run_map.get(r["serpapi_run_id"]), "triggered_by": r["triggered_by"]}], ret=True)
    rr_map[r["id"]] = res[0]["id"]

rk_rows = rows("SELECT * FROM keyword_rankings")
res = post("keyword_rankings", [{
    "run_id": rr_map[k["run_id"]], "keyword_id": kw_map[k["keyword_id"]], "rank": k["rank"],
    "total_score": k["total_score"], "score_coverage": k["score_coverage"],
    "score_competitor": k["score_competitor"], "score_freshness": k["score_freshness"],
    "score_serpapi_trend": k["score_serpapi_trend"], "total_articles_found": k["total_articles_found"],
    "press_count": k["press_count"], "competitor_count": k["competitor_count"],
    "newest_hours_ago": k["newest_hours_ago"], "is_trending_now": b(k["is_trending_now"]),
    "google_trends_index": k["google_trends_index"] or 0} for k in rk_rows], "run_id,keyword_id", ret=True)
rk_map = {k["id"]: next(x["id"] for x in res if x["run_id"] == rr_map[k["run_id"]]
                        and x["keyword_id"] == kw_map[k["keyword_id"]]) for k in rk_rows}

post("ranking_articles", [{"ranking_id": rk_map[x["ranking_id"]], "article_id": art_map[x["article_id"]],
                           "position": x["position"]} for x in rows("SELECT * FROM ranking_articles")],
     "ranking_id,position")

# ignore-duplicates để KHÔNG ghi đè status/assignee mà bạn đã chỉnh trên Supabase
post("seo_suggestions", [{
    "ranking_id": rk_map[s["ranking_id"]], "keyword": s["keyword"], "intent": s["intent"],
    "based_on_article": art_map.get(s["based_on_article"]), "based_on_text": s["based_on_text"],
    "status": s["status"], "assignee": s["assignee"], "published_url": s["published_url"],
    "published_at": s["published_at"], "note": s["note"], "created_at": s["created_at"]}
    for s in rows("SELECT * FROM seo_suggestions")], "ranking_id,keyword", ignore=True)

# 6. Đối chiếu số dòng
print("\nĐối chiếu số dòng (SQLite -> Supabase):")
ok = True
for t in ["niches", "sources", "articles", "keywords", "article_keywords", "report_runs", "keyword_rankings",
          "ranking_articles", "seo_suggestions", "serpapi_runs", "serpapi_calls", "trending_queries",
          "trending_related_queries", "autocomplete_suggestions", "google_trends_scores", "serpapi_quota_snapshots"]:
    local = db.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
    r = requests.get(f"{URL}/rest/v1/{t}?select=*&limit=1", headers={**HEADERS, "Prefer": "count=exact"}, timeout=30)
    remote = int(r.headers.get("content-range", "*/0").split("/")[-1])
    flag = "OK" if local == remote else "LỆCH"
    ok &= local == remote
    print(f"  {t:28} {local:5} -> {remote:5}  {flag}")
print("\nHOÀN TẤT" if ok else "\nCó bảng lệch số dòng, kiểm tra lại.")
