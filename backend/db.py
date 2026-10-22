# -*- coding: utf-8 -*-
"""
Lớp lưu trữ SQLite cho hệ thống: bài viết, keyword, lịch sử Top 10, gợi ý SEO và dữ liệu SerpApi.
Schema nằm ở database/schema.sql. File DB: data/tnc.db
"""

import hashlib
import json
import re
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

from backend.classifier import NICHES

VN_TZ = timezone(timedelta(hours=7))
BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "data" / "tnc.db"
SCHEMA_PATH = BASE_DIR / "database" / "schema.sql"

ENGINE_BY_API_KEY = {
    "google_trends_trending_now": "google_trends_trending_now",
    "google_autocomplete": "google_autocomplete",
    "google_search": "google",
    "google_trends": "google_trends",
}
SEO_STATUSES = {"NEW", "PLANNED", "WRITING", "PUBLISHED", "SKIPPED"}


def _now_iso() -> str:
    return datetime.now(VN_TZ).isoformat(timespec="seconds")


def connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


@contextmanager
def session():
    """Mở kết nối, tự đảm bảo schema, commit khi thành công / rollback khi lỗi."""
    conn = connect()
    try:
        init_schema(conn)
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _migrate_ranking_positions(conn: sqlite3.Connection) -> None:
    """DB cũ giới hạn position 1..3; nâng lên 1..5 để lưu được Top 5 bài viết (giữ nguyên dữ liệu cũ)."""
    row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='ranking_articles'"
    ).fetchone()
    if not row or "BETWEEN 1 AND 3" not in (row["sql"] or ""):
        return
    conn.execute("ALTER TABLE ranking_articles RENAME TO ranking_articles_old")
    conn.execute(
        """CREATE TABLE ranking_articles (
               ranking_id  INTEGER NOT NULL REFERENCES keyword_rankings(id) ON DELETE CASCADE,
               article_id  INTEGER NOT NULL REFERENCES articles(id),
               position    INTEGER NOT NULL CHECK (position BETWEEN 1 AND 5),
               PRIMARY KEY (ranking_id, position)
           )"""
    )
    conn.execute("INSERT INTO ranking_articles SELECT ranking_id, article_id, position FROM ranking_articles_old")
    conn.execute("DROP TABLE ranking_articles_old")


def init_schema(conn: sqlite3.Connection) -> None:
    exists = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='articles'"
    ).fetchone()
    if exists:
        _migrate_ranking_positions(conn)
        return
    conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
    for n in NICHES.values():
        conn.execute(
            "INSERT OR IGNORE INTO niches(id, name, badge_color, group_name) VALUES (?,?,?,?)",
            (n["id"], n["name"], n.get("badge_color"), n.get("group")),
        )


# ---------------------------------------------------------------------------
# Bài viết / nguồn
# ---------------------------------------------------------------------------
def _title_hash(title: str) -> str:
    norm = re.sub(r"\W+", "", (title or "").lower())[:60]
    return hashlib.md5(norm.encode("utf-8")).hexdigest()


def _niche_id(niche: Any) -> Optional[str]:
    if isinstance(niche, dict):
        niche = niche.get("id")
    return niche if niche in NICHES else None


def _source_id(conn, art: Dict) -> int:
    name = art.get("source_name") or "Không rõ nguồn"
    row = conn.execute("SELECT id FROM sources WHERE name=?", (name,)).fetchone()
    if row:
        return row["id"]
    stype = art.get("source_type") if art.get("source_type") in ("PRESS", "COMPETITOR", "OWN") else "PRESS"
    cur = conn.execute(
        "INSERT INTO sources(name, source_type, badge) VALUES (?,?,?)",
        (name, stype, art.get("source_badge")),
    )
    return cur.lastrowid


def upsert_article(conn, art: Dict) -> Optional[int]:
    url = (art.get("url") or "").strip()
    title = art.get("title") or ""
    if not url or not title:
        return None
    row = conn.execute("SELECT id FROM articles WHERE url=?", (url,)).fetchone()
    niche = art.get("niche")
    niche_id = _niche_id(niche)
    relevance = niche.get("relevance_score") if isinstance(niche, dict) else None
    if row:
        conn.execute(
            "UPDATE articles SET niche_id=COALESCE(?, niche_id), niche_relevance=COALESCE(?, niche_relevance) WHERE id=?",
            (niche_id, relevance, row["id"]),
        )
        return row["id"]
    cur = conn.execute(
        """INSERT INTO articles(source_id, url, title, title_norm_hash, summary, published_at,
                                fetched_at, origin, niche_id, niche_relevance)
           VALUES (?,?,?,?,?,?,?,?,?,?)""",
        (
            _source_id(conn, art), url, title, _title_hash(title), art.get("summary") or "",
            art.get("published_at") or _now_iso(), _now_iso(),
            "SERPAPI_SEARCH" if art.get("from_serpapi_search") else "RSS",
            niche_id, relevance,
        ),
    )
    return cur.lastrowid


def _upsert_keyword(conn, cluster_id: str, display: str, niche: Any) -> int:
    now = _now_iso()
    row = conn.execute("SELECT id FROM keywords WHERE cluster_id=?", (cluster_id,)).fetchone()
    if row:
        conn.execute(
            "UPDATE keywords SET display_keyword=?, niche_id=COALESCE(?, niche_id), last_seen_at=? WHERE id=?",
            (display, _niche_id(niche), now, row["id"]),
        )
        return row["id"]
    cur = conn.execute(
        "INSERT INTO keywords(cluster_id, display_keyword, niche_id, first_seen_at, last_seen_at) VALUES (?,?,?,?,?)",
        (cluster_id, display, _niche_id(niche), now, now),
    )
    return cur.lastrowid


# ---------------------------------------------------------------------------
# SerpApi
# ---------------------------------------------------------------------------
def save_serpapi(conn, serp: Dict[str, Any]) -> Optional[int]:
    """Lưu kết quả 4 cổng SerpApi của 1 ngày. Trả về serpapi_runs.id (None nếu không có dữ liệu)."""
    date_str = (serp.get("date") or "")[:10]
    apis = serp.get("apis_called") or {}
    if not date_str or not apis:
        return None

    row = conn.execute("SELECT id FROM serpapi_runs WHERE run_date=?", (date_str,)).fetchone()
    if row and serp.get("from_cache"):
        return row["id"]  # bản cache: DB đã có sẵn, không ghi lại

    if row:
        run_id = row["id"]
        conn.execute("DELETE FROM serpapi_calls WHERE serpapi_run=?", (run_id,))
        conn.execute("UPDATE serpapi_runs SET executed_at=?, forced=1 WHERE id=?", (_now_iso(), run_id))
    else:
        run_id = conn.execute(
            "INSERT INTO serpapi_runs(run_date, executed_at, forced) VALUES (?,?,0)",
            (date_str, serp.get("date") or _now_iso()),
        ).lastrowid

    payload_by_engine = {
        "google_trends_trending_now": serp.get("trending_now_items", []),
        "google_autocomplete": serp.get("autocomplete_suggestions", []),
        "google": serp.get("google_search_articles", []),
        "google_trends": serp.get("google_trends_scores", {}),
    }

    for api_key, info in apis.items():
        engine = ENGINE_BY_API_KEY.get(api_key)
        if not engine:
            continue
        payload = payload_by_engine[engine]
        call_id = conn.execute(
            """INSERT INTO serpapi_calls(serpapi_run, engine, query, status, result_count, error_message, raw_json)
               VALUES (?,?,?,?,?,?,?)""",
            (
                run_id, engine, info.get("query") or info.get("seed_query"),
                info.get("status", "unknown"), len(payload) if payload else 0,
                info.get("message"), json.dumps(payload, ensure_ascii=False),
            ),
        ).lastrowid

        if engine == "google_trends_trending_now":
            for t in payload:
                tid = conn.execute(
                    """INSERT INTO trending_queries(call_id, query, search_volume, increase_percentage, categories)
                       VALUES (?,?,?,?,?)""",
                    (call_id, t.get("query", ""), t.get("search_volume"), t.get("increase_percentage"),
                     json.dumps(t.get("categories", []), ensure_ascii=False)),
                ).lastrowid
                for rq in t.get("related_queries", []):
                    if isinstance(rq, str):
                        conn.execute(
                            "INSERT OR IGNORE INTO trending_related_queries(trending_id, related) VALUES (?,?)",
                            (tid, rq),
                        )
        elif engine == "google_autocomplete":
            for s in payload:
                conn.execute(
                    "INSERT INTO autocomplete_suggestions(call_id, seed, suggestion) VALUES (?,?,?)",
                    (call_id, info.get("seed_query", ""), s),
                )
        elif engine == "google_trends":
            for q, v in payload.items():
                conn.execute(
                    "INSERT OR REPLACE INTO google_trends_scores(call_id, query, score) VALUES (?,?,?)",
                    (call_id, q, int(v or 0)),
                )
    return run_id


def save_quota(conn, account: Dict[str, Any]) -> None:
    if not isinstance(account, dict) or not isinstance(account.get("searches_left"), int):
        return
    conn.execute(
        """INSERT INTO serpapi_quota_snapshots(captured_at, plan_name, searches_left, searches_per_month, this_month_usage)
           VALUES (?,?,?,?,?)""",
        (_now_iso(), account.get("plan_name"), account.get("searches_left"),
         account.get("searches_per_month"), account.get("this_month_usage")),
    )


# ---------------------------------------------------------------------------
# Báo cáo Top 10
# ---------------------------------------------------------------------------
def _report_time_iso(generated_at: str) -> str:
    try:
        return datetime.strptime(generated_at, "%d/%m/%Y %H:%M:%S").replace(tzinfo=VN_TZ).isoformat(timespec="seconds")
    except Exception:
        return _now_iso()


def save_report(conn, report: Dict[str, Any], serpapi_run_id: Optional[int] = None,
                triggered_by: str = "manual") -> int:
    generated_iso = _report_time_iso(report.get("generated_at", ""))
    run_id = conn.execute(
        """INSERT INTO report_runs(generated_at, time_window_hours, total_articles_scanned,
                                   total_clusters, serpapi_run_id, triggered_by)
           VALUES (?,?,?,?,?,?)""",
        (generated_iso, report.get("time_window_hours", 48), report.get("total_articles_scanned"),
         report.get("total_clusters_detected"), serpapi_run_id, triggered_by),
    ).lastrowid

    for item in report.get("top_10_keywords", []):
        kw_id = _upsert_keyword(conn, item["cluster_id"], item["keyword"], item.get("niche"))
        bd, st = item.get("score_breakdown", {}), item.get("stats", {})
        rank_id = conn.execute(
            """INSERT INTO keyword_rankings(run_id, keyword_id, rank, total_score, score_coverage,
                   score_competitor, score_freshness, score_serpapi_trend, total_articles_found,
                   press_count, competitor_count, newest_hours_ago, is_trending_now, google_trends_index)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (run_id, kw_id, item["rank"], item["total_score"], bd.get("coverage"), bd.get("competitor"),
             bd.get("freshness"), bd.get("serpapi_trend"), st.get("total_articles_found"),
             st.get("press_count"), st.get("competitor_count"), st.get("newest_hours_ago"),
             1 if st.get("is_trending_now") else 0, st.get("google_trends_index") or 0),
        ).lastrowid

        article_ids: Dict[str, int] = {}
        for pos, art in enumerate(item.get("top_3_articles", [])[:5], start=1):
            aid = upsert_article(conn, art)
            if aid is None:
                continue
            article_ids[art.get("title", "")] = aid
            conn.execute("INSERT OR IGNORE INTO ranking_articles(ranking_id, article_id, position) VALUES (?,?,?)",
                         (rank_id, aid, pos))
            conn.execute("INSERT OR IGNORE INTO article_keywords(article_id, keyword_id) VALUES (?,?)", (aid, kw_id))

        for sug in item.get("seo_suggested_keywords", []):
            based_on = sug.get("based_on", "")
            based_id = next((aid for t, aid in article_ids.items() if t and t in based_on), None)
            conn.execute(
                """INSERT OR IGNORE INTO seo_suggestions(ranking_id, keyword, intent, based_on_article,
                                                         based_on_text, created_at)
                   VALUES (?,?,?,?,?,?)""",
                (rank_id, sug.get("keyword", ""), sug.get("intent"), based_id, based_on, _now_iso()),
            )
    return run_id


def persist_run(report: Dict[str, Any], serp: Dict[str, Any], articles: List[Dict],
                triggered_by: str = "manual") -> int:
    """Điểm vào duy nhất cho engine: ghi toàn bộ 1 lần chạy trong 1 transaction."""
    with session() as conn:
        for art in articles:
            upsert_article(conn, art)
        serp_id = save_serpapi(conn, serp)
        save_quota(conn, report.get("serpapi_status", {}).get("account", {}))
        return save_report(conn, report, serp_id, triggered_by)


# ---------------------------------------------------------------------------
# Truy vấn cho API
# ---------------------------------------------------------------------------
def keyword_history(keyword: str, limit: int = 30) -> List[Dict]:
    with session() as conn:
        rows = conn.execute(
            """SELECT r.generated_at, kr.rank, kr.total_score, kr.score_coverage, kr.score_competitor,
                      kr.score_freshness, kr.score_serpapi_trend
               FROM keyword_rankings kr
               JOIN keywords k ON k.id = kr.keyword_id
               JOIN report_runs r ON r.id = kr.run_id
               WHERE k.display_keyword LIKE ? OR k.cluster_id LIKE ?
               ORDER BY r.generated_at DESC LIMIT ?""",
            (f"%{keyword}%", f"%{keyword}%", limit),
        ).fetchall()
        return [dict(r) for r in rows]


def list_suggestions(status: Optional[str] = None, limit: int = 100) -> List[Dict]:
    with session() as conn:
        sql = """SELECT s.id, s.keyword, s.intent, s.status, s.assignee, s.published_url, s.note,
                        s.based_on_text, k.display_keyword AS topic, r.generated_at
                 FROM seo_suggestions s
                 JOIN keyword_rankings kr ON kr.id = s.ranking_id
                 JOIN keywords k ON k.id = kr.keyword_id
                 JOIN report_runs r ON r.id = kr.run_id"""
        params: list = []
        if status:
            sql += " WHERE s.status=?"
            params.append(status)
        sql += " ORDER BY r.generated_at DESC, kr.rank LIMIT ?"
        params.append(limit)
        return [dict(r) for r in conn.execute(sql, params).fetchall()]


def update_suggestion(suggestion_id: int, fields: Dict[str, Any]) -> bool:
    allowed = {"status", "assignee", "published_url", "note"}
    data = {k: v for k, v in fields.items() if k in allowed}
    if "status" in data:
        if data["status"] not in SEO_STATUSES:
            raise ValueError(f"status phải thuộc {sorted(SEO_STATUSES)}")
        if data["status"] == "PUBLISHED":
            data["published_at"] = _now_iso()
    if not data:
        return False
    sets = ", ".join(f"{k}=?" for k in data)
    with session() as conn:
        cur = conn.execute(f"UPDATE seo_suggestions SET {sets} WHERE id=?", (*data.values(), suggestion_id))
        return cur.rowcount > 0
