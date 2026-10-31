# -*- coding: utf-8 -*-
"""Kéo số liệu thật từ Google Search Console + GA4 cho các bài của trang, ghi vào Supabase để tab BÁO CÁO hiển thị.

Nguồn bài:
  1. Danh mục Tin tức của trang (https://www.tnc.com.vn/tin-tuc.html và các danh mục con): bài đăng trong NEWS_WINDOW_DAYS ngày gần nhất.
  2. Bài của dashboard (seo_articles.published_url): luôn được theo dõi, đánh dấu is_dashboard = true.
Đích:   bảng seo_article_metrics (database/seo_article_metrics.sql)
Gồm:    clicks / impressions / vị trí theo ngày (60 ngày), top query, thiết bị, GA4 (sessions...), trạng thái Google Index.

Mặc định chỉ XEM TRƯỚC (không ghi). Thêm --apply để ghi thật.

Biến môi trường (.env): SUPABASE_URL, SUPABASE_SERVICE_KEY.
Tùy chọn: GOOGLE_SERVICE_ACCOUNT_JSON (đường dẫn file hoặc nội dung JSON; mặc định dùng khóa của seo-audit-tool),
          GSC_SITE_URL, GA4_PROPERTY_ID, SYNC_WORKERS (số luồng, mặc định 6),
          NEWS_HUB_URL (mặc định https://www.tnc.com.vn/tin-tuc.html), NEWS_WINDOW_DAYS (mặc định 60).
Chạy:  python sync_gsc_ga4.py            (xem trước)
       python sync_gsc_ga4.py --apply    (ghi lên Supabase)
"""
import html
import json
import os
import re
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import quote, urljoin, urlparse

import requests
from dotenv import load_dotenv
from google.auth.transport.requests import AuthorizedSession
from google.oauth2 import service_account

ROOT = Path(__file__).resolve().parent
DEFAULT_KEY = ROOT.parent / "seo-audit-tool" / "storage" / "credentials" / "google-service-account.json"
DEFAULT_SITE = "https://www.tnc.com.vn/"
DEFAULT_GA4 = "286857049"
DEFAULT_HUB = "https://www.tnc.com.vn/tin-tuc.html"
SCOPES = [
    "https://www.googleapis.com/auth/webmasters.readonly",
    "https://www.googleapis.com/auth/analytics.readonly",
]
HISTORY_DAYS = 60
GSC_LAG_DAYS = 0  # lấy đến hôm nay (giờ VN); GSC với dataState=all chỉ trả đến ~hôm qua, ngày chưa chốt sẽ được ghi đè ở lần đồng bộ sau
MAX_LIST_PAGES = 40  # chặn vòng lặp phân trang
UA = {"User-Agent": "Mozilla/5.0 (TNC SEO report sync)"}


def need(name: str) -> str:
    val = os.getenv(name, "").strip()
    if not val:
        sys.exit(f"Thiếu biến môi trường {name}.")
    return val


# ----------------------------------------------------------------------------- quét danh mục tin tức
CARD_RE = re.compile(
    r"<a href=['\"]([^'\"]+)['\"] class=['\"]cr-blog-classic-inner['\"]>.*?<h3>(.*?)</h3>.*?class=['\"]cr-date['\"]>(\d{2}-\d{2}-\d{4})<",
    re.S,
)
CATEGORY_RE = re.compile(r"<h2>([^<]+)</h2>\s*<a href=\"([^\"]+)\" class=\"xem-them\"", re.S)


def fetch(url: str) -> str:
    r = requests.get(url, headers=UA, timeout=30)
    r.raise_for_status()
    return r.text


def clean_url(site: str, href: str) -> str:
    u = urljoin(site, href.strip())
    return u.split("#")[0].split("?")[0]


def crawl_news(hub_url: str, site: str, cutoff: date) -> dict:
    """Trả về {url: {title, published_date, category}} cho bài đăng từ cutoff đến nay."""
    found = {}
    cats = CATEGORY_RE.findall(fetch(hub_url))
    if not cats:
        sys.exit(f"Không đọc được danh mục con từ {hub_url} (cấu trúc trang đã đổi?).")
    for name, href in cats:
        cat_url = clean_url(site, href)
        name = html.unescape(name).strip()
        total = 0
        for page in range(1, MAX_LIST_PAGES + 1):
            cards = CARD_RE.findall(fetch(f"{cat_url}?p={page}"))
            if not cards:
                break
            dates = []
            for h, title, d in cards:
                pub = datetime.strptime(d, "%d-%m-%Y").date()
                dates.append(pub)
                if pub >= cutoff:
                    found.setdefault(clean_url(site, h), {"title": html.unescape(re.sub(r"<[^>]+>", "", title)).strip(),
                                                          "published_date": pub.isoformat(), "category": name})
                    total += 1
            if max(dates) < cutoff:  # danh sách xếp mới -> cũ, cả trang đã quá hạn thì dừng
                break
            time.sleep(0.4)
        print(f"  Danh mục {name}: {total} bài trong {(date.today() - cutoff).days} ngày")
    return found


# ----------------------------------------------------------------------------- Google
class Google:
    def __init__(self, key: str, site_url: str, ga4_property: str):
        """key: đường dẫn file JSON, hoặc chính nội dung JSON (dùng cho GitHub Actions Secrets)."""
        if key.lstrip().startswith("{"):
            self.creds = service_account.Credentials.from_service_account_info(json.loads(key), scopes=SCOPES)
        elif Path(key).is_file():
            self.creds = service_account.Credentials.from_service_account_file(key, scopes=SCOPES)
        else:
            sys.exit(f"Không thấy file khóa service account: {key} (đặt GOOGLE_SERVICE_ACCOUNT_JSON trong .env)")
        self.email = self.creds.service_account_email
        self.site = site_url
        self.ga4 = ga4_property
        self._local = threading.local()  # mỗi luồng một phiên HTTP riêng

    @property
    def session(self) -> AuthorizedSession:
        if not hasattr(self._local, "s"):
            self._local.s = AuthorizedSession(self.creds)
        return self._local.s

    def _post(self, url: str, body: dict) -> dict:
        for attempt in range(3):
            r = self.session.post(url, json=body, timeout=60)
            if r.status_code in (429, 500, 502, 503) and attempt < 2:
                time.sleep(2 * (attempt + 1))
                continue
            if r.status_code >= 300:
                raise RuntimeError(f"{r.status_code}: {r.text[:300]}")
            return r.json()

    def gsc(self, start: date, end: date, dimensions: list, page: str, limit: int = 1000) -> list:
        url = f"https://searchconsole.googleapis.com/webmasters/v3/sites/{quote(self.site, safe='')}/searchAnalytics/query"
        body = {
            "startDate": start.isoformat(), "endDate": end.isoformat(), "dimensions": dimensions, "rowLimit": limit,
            "dataState": "all",  # gồm cả số liệu chưa chốt của 1-2 ngày gần nhất (mặc định chỉ trả số đã chốt, trễ 2-3 ngày)
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
            # landingPage của GA4 gồm cả tham số (?fbclid=, ?utm_...) nên khớp theo đầu chuỗi rồi lọc lại đúng đường dẫn
            "dimensionFilter": {"filter": {"fieldName": "landingPage", "stringFilter": {"matchType": "BEGINS_WITH", "value": path}}},
            "limit": "1000",
        }
        rows = [r for r in self._post(url, body).get("rows", [])
                if r["dimensionValues"][0]["value"].split("?")[0].split("#")[0] in (path, path.rstrip("/"), path.rstrip("/") + "/")]
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
        key = "clicks" if sum(r["clicks"] for r in drows) else "impressions"
        total = sum(r[key] for r in drows)
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
    site = os.getenv("GSC_SITE_URL", "").strip() or DEFAULT_SITE
    g = Google(os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON", "").strip() or str(DEFAULT_KEY),
               site, os.getenv("GA4_PROPERTY_ID", "").strip() or DEFAULT_GA4)
    window = int(os.getenv("NEWS_WINDOW_DAYS", "").strip() or HISTORY_DAYS)
    hub = os.getenv("NEWS_HUB_URL", "").strip() or DEFAULT_HUB
    print(f"Service account: {g.email}\nGSC: {g.site} · GA4: {g.ga4}\nQuét bài đăng trong {window} ngày từ {hub}")

    headers = {"apikey": sb_key, "Authorization": f"Bearer {sb_key}", "Content-Type": "application/json"}
    r = requests.get(f"{sb_url}/rest/v1/seo_articles?select=id,keyword,title,published_url&published_url=not.is.null",
                     headers=headers, timeout=60)
    if r.status_code >= 300:
        sys.exit(f"Không đọc được seo_articles ({r.status_code}): {r.text[:300]}")
    dash = {a["published_url"].strip(): a for a in r.json() if (a.get("published_url") or "").strip()}

    news = crawl_news(hub, site, date.today() - timedelta(days=window))
    targets = {}
    for u, meta in news.items():
        targets[u] = {**meta, "is_dashboard": False, "article_id": None}
    for u, a in dash.items():
        t = targets.setdefault(u, {"title": a.get("title") or a["keyword"], "published_date": None, "category": None})
        t.update(is_dashboard=True, article_id=a["id"])
    print(f"Tổng {len(targets)} bài cần theo dõi ({len(news)} từ trang, {len(dash)} từ dashboard, "
          f"{sum(1 for t in targets.values() if t['is_dashboard'])} bài dashboard)")

    # Runner GitHub chạy giờ UTC: 06:00 VN = 23:00 UTC hôm trước nên date.today() bị lùi 1 ngày, dùng ngày VN
    end = datetime.now(timezone(timedelta(hours=7))).date() - timedelta(days=GSC_LAG_DAYS)
    rows = []
    workers = int(os.getenv("SYNC_WORKERS", "").strip() or 6)
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(collect, g, url, end): (url, meta) for url, meta in targets.items()}
        for n, fut in enumerate(as_completed(futures), 1):
            url, meta = futures[fut]
            tag = " [DASHBOARD]" if meta["is_dashboard"] else ""
            try:
                row = fut.result()
            except Exception as e:
                print(f"[{n}/{len(targets)}]{tag} x Lỗi, bỏ qua {url}: {e}")
                continue
            row.update(title=meta["title"], published_date=meta["published_date"], category=meta["category"],
                       is_dashboard=meta["is_dashboard"], article_id=meta["article_id"])
            print(f"[{n}/{len(targets)}]{tag} {meta['title'][:60]} · {len(row['daily'])} ngày có dữ liệu · index: {row['index_state'] or row['is_indexed']}")
            rows.append(row)

    # Ngày cuối của dữ liệu = ngày GSC thật sự có số (GSC chưa có hôm nay), nếu không dashboard vẽ thêm một ngày trống
    # và so kỳ này với kỳ trước bị lệch.
    last_gsc = max((d["d"] for r in rows for d in r["daily"]), default=None)
    if last_gsc:
        for r in rows:
            r["data_end_date"] = last_gsc

    if apply and rows:
        for i in range(0, len(rows), 20):
            p = requests.post(f"{sb_url}/rest/v1/seo_article_metrics?on_conflict=url",
                              headers={**headers, "Prefer": "resolution=merge-duplicates,return=minimal"}, json=rows[i:i + 20], timeout=90)
            if p.status_code >= 300:
                sys.exit(f"Không ghi được lô {i // 20 + 1} ({p.status_code}): {p.text[:300]} (đã chạy lại database/seo_article_metrics.sql chưa?)")
        # Xóa bài trang đã quá hạn (không còn trong cửa sổ và không phải bài dashboard)
        ex = requests.get(f"{sb_url}/rest/v1/seo_article_metrics?select=url&is_dashboard=eq.false", headers=headers, timeout=60)
        if ex.status_code < 300:
            for old in (x["url"] for x in ex.json() if x["url"] not in targets):
                requests.delete(f"{sb_url}/rest/v1/seo_article_metrics", headers=headers, params={"url": f"eq.{old}"}, timeout=60)
                print(f"  Đã gỡ bài quá hạn: {old}")
    print(f"{'Đã ghi' if apply else 'Sẽ ghi'} {len(rows)}/{len(targets)} bài." + ("" if apply else "  Thêm --apply để ghi thật."))


if __name__ == "__main__":
    main()
