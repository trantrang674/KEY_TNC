# -*- coding: utf-8 -*-
"""Kéo số liệu thật từ Google Search Console + GA4 cho các bài đã đăng, ghi vào Supabase để tab BÁO CÁO hiển thị.

Nguồn:  seo_articles.published_url (các bài đã có link đăng trên tab WORKFLOW)
Đích:   bảng seo_article_metrics (tạo bằng database/seo_article_metrics.sql)
Gồm:    clicks / impressions / vị trí theo ngày (90 ngày), top query, thiết bị, GA4 (sessions...), trạng thái Google Index.

Mặc định chỉ XEM TRƯỚC (không ghi). Thêm --apply để ghi thật.

Biến môi trường (.env): SUPABASE_URL, SUPABASE_SERVICE_KEY.
Tùy chọn: GOOGLE_SERVICE_ACCOUNT_JSON (mặc định dùng khóa của seo-audit-tool), GSC_SITE_URL, GA4_PROPERTY_ID.
Chạy:  python sync_gsc_ga4.py            (xem trước)
       python sync_gsc_ga4.py --apply    (ghi lên Supabase)
"""
import os
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import quote, urlparse

import requests
from dotenv import load_dotenv
from google.auth.transport.requests import AuthorizedSession
from google.oauth2 import service_account

ROOT = Path(__file__).resolve().parent
DEFAULT_KEY = ROOT.parent / "seo-audit-tool" / "storage" / "credentials" / "google-service-account.json"
DEFAULT_SITE = "https://www.tnc.com.vn/"
DEFAULT_GA4 = "286857049"
SCOPES = [
    "https://www.googleapis.com/auth/webmasters.readonly",
    "https://www.googleapis.com/auth/analytics.readonly",
]
HISTORY_DAYS = 90
GSC_LAG_DAYS = 3  # GSC thường trễ 2-3 ngày mới có số liệu chốt


def need(name: str) -> str:
    val = os.getenv(name, "").strip()
    if not val:
        sys.exit(f"Thiếu biến môi trường {name}.")
    return val


class Google:
    def __init__(self, key_path: Path, site_url: str, ga4_property: str):
        if not key_path.is_file():
            sys.exit(f"Không thấy file khóa service account: {key_path} (đặt GOOGLE_SERVICE_ACCOUNT_JSON trong .env)")
        creds = service_account.Credentials.from_service_account_file(str(key_path), scopes=SCOPES)
        self.session = AuthorizedSession(creds)
        self.email = creds.service_account_email
        self.site = site_url
        self.ga4 = ga4_property

    def _post(self, url: str, body: dict) -> dict:
        r = self.session.post(url, json=body, timeout=60)
        if r.status_code >= 300:
            raise RuntimeError(f"{r.status_code}: {r.text[:300]}")
        return r.json()

    def gsc(self, start: date, end: date, dimensions: list, page: str, limit: int = 1000) -> list:
        url = f"https://searchconsole.googleapis.com/webmasters/v3/sites/{quote(self.site, safe='')}/searchAnalytics/query"
        body = {
            "startDate": start.isoformat(), "endDate": end.isoformat(), "dimensions": dimensions, "rowLimit": limit,
            "dimensionFilterGroups": [{"filters": [{"dimension": "page", "operator": "equals", "expression": page}]}],
        }
        return self._post(url, body).get("rows", [])

    def inspect(self, page: str) -> dict:
        url = "https://searchconsole.googleapis.com/v1/urlInspection/index:inspect"
        data = self._post(url, {"inspectionUrl": page, "siteUrl": self.site, "languageCode": "vi"})
        return (data.get("inspectionResult") or {}).get("indexStatusResult") or {}

    def ga4_landing(self, path: str, start: date, end: date) -> dict:
        url = f"https://analyticsdata.googleapis.com/v1beta/properties/{self.ga4}:runReport"
        body = {
            "dateRanges": [{"startDate": start.isoformat(), "endDate": end.isoformat()}],
            "dimensions": [{"name": "landingPage"}],
            "metrics": [{"name": "sessions"}, {"name": "engagementRate"}, {"name": "averageSessionDuration"}, {"name": "keyEvents"}],
            "dimensionFilter": {"filter": {"fieldName": "landingPage", "stringFilter": {"matchType": "EXACT", "value": path}}},
            "limit": "10",
        }
        rows = self._post(url, body).get("rows", [])
        sessions = sum(float(r["metricValues"][0]["value"]) for r in rows)
        if not sessions:
            return {"sessions": 0, "engagement_rate": 0, "avg_duration": 0, "key_events": 0}
        w = lambda i: sum(float(r["metricValues"][i]["value"]) * float(r["metricValues"][0]["value"]) for r in rows) / sessions
        return {
            "sessions": int(sessions), "engagement_rate": round(w(1) * 100, 1), "avg_duration": round(w(2), 1),
            "key_events": int(sum(float(r["metricValues"][3]["value"]) for r in rows)),
        }


def url_variants(url: str) -> list:
    """GSC khớp URL tuyệt đối, nên thử thêm biến thể có/không dấu / ở cuối."""
    alt = url[:-1] if url.endswith("/") else url + "/"
    return [url, alt]


def collect(g: Google, url: str, end: date) -> dict:
    start = end - timedelta(days=HISTORY_DAYS - 1)
    d28 = end - timedelta(days=27)
    daily, used = [], url
    for v in url_variants(url):
        rows = g.gsc(start, end, ["date"], v)
        if rows:
            used = v
            daily = [{"d": r["keys"][0], "c": int(r["clicks"]), "i": int(r["impressions"]), "p": round(r["position"], 1)} for r in rows]
            break

    queries, device = [], {}
    if daily:
        qrows = g.gsc(d28, end, ["query"], used, limit=10)
        queries = [{"query": r["keys"][0], "clicks": int(r["clicks"]), "impr": int(r["impressions"]),
                    "ctr": round(r["ctr"] * 100, 1), "rank": max(1, round(r["position"]))} for r in qrows]
        drows = g.gsc(d28, end, ["device"], used)
        total = sum(r["clicks"] for r in drows) or sum(r["impressions"] for r in drows)
        key = "clicks" if sum(r["clicks"] for r in drows) else "impressions"
        if total:
            device = {r["keys"][0].lower(): round(r[key] / total * 100) for r in drows}

    path = urlparse(url).path or "/"
    ga4 = {}
    try:
        ga4 = {"7d": g.ga4_landing(path, end - timedelta(days=6), end), "28d": g.ga4_landing(path, d28, end)}
    except Exception as e:  # GA4 lỗi không được làm hỏng phần GSC
        print(f"    ! GA4: {e}")

    is_indexed, state, crawl = None, None, None
    try:
        st = g.inspect(used)
        state, crawl = st.get("coverageState"), st.get("lastCrawlTime")
        is_indexed = st.get("verdict") == "PASS"
    except Exception as e:
        print(f"    ! Kiểm tra index: {e}")
        if daily:
            is_indexed = True  # đã có impressions thì chắc chắn đã index

    return {
        "url": url, "daily": daily, "queries": queries, "device": device, "ga4": ga4,
        "is_indexed": is_indexed, "index_state": state, "last_crawl_time": crawl,
        "data_end_date": end.isoformat(), "synced_at": datetime.now(timezone.utc).isoformat(),
    }


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    load_dotenv(ROOT / ".env")
    sb_url = need("SUPABASE_URL").rstrip("/")
    sb_key = need("SUPABASE_SERVICE_KEY")
    apply = "--apply" in sys.argv
    g = Google(Path(os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON", "").strip() or DEFAULT_KEY),
               os.getenv("GSC_SITE_URL", "").strip() or DEFAULT_SITE,
               os.getenv("GA4_PROPERTY_ID", "").strip() or DEFAULT_GA4)
    print(f"Service account: {g.email}\nGSC: {g.site} · GA4: {g.ga4}")

    headers = {"apikey": sb_key, "Authorization": f"Bearer {sb_key}", "Content-Type": "application/json"}
    r = requests.get(f"{sb_url}/rest/v1/seo_articles?select=id,keyword,published_url&published_url=not.is.null",
                     headers=headers, timeout=60)
    if r.status_code >= 300:
        sys.exit(f"Không đọc được seo_articles ({r.status_code}): {r.text[:300]}")
    articles = [a for a in r.json() if (a.get("published_url") or "").strip()]
    if not articles:
        sys.exit("Chưa có bài nào có link đã đăng (nhập link ở tab WORKFLOW rồi chạy lại).")

    end = date.today() - timedelta(days=GSC_LAG_DAYS)
    ok = 0
    for a in articles:
        url = a["published_url"].strip()
        print(f"- {a['keyword']}: {url}")
        try:
            row = collect(g, url, end)
        except Exception as e:
            print(f"    x Lỗi, bỏ qua: {e}")
            continue
        row["article_id"] = a["id"]
        c7 = sum(d["c"] for d in row["daily"][-7:])
        print(f"    {len(row['daily'])} ngày có dữ liệu · clicks 7 ngày cuối: {c7} · index: {row['index_state'] or row['is_indexed']}")
        if not row["daily"]:
            print("    (GSC chưa có số liệu cho URL này: bài mới đăng hoặc URL không khớp property)")
        if apply:
            p = requests.post(f"{sb_url}/rest/v1/seo_article_metrics?on_conflict=url",
                              headers={**headers, "Prefer": "resolution=merge-duplicates,return=minimal"}, json=row, timeout=60)
            if p.status_code >= 300:
                sys.exit(f"Không ghi được {url} ({p.status_code}): {p.text[:300]} (đã chạy database/seo_article_metrics.sql chưa?)")
        ok += 1
    print(f"{'Đã ghi' if apply else 'Sẽ ghi'} {ok}/{len(articles)} bài." + ("" if apply else "  Thêm --apply để ghi thật."))


if __name__ == "__main__":
    main()
