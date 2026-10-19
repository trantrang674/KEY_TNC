# -*- coding: utf-8 -*-
"""
Module tích hợp 4 cổng SerpApi (đúng 1 lượt gọi cho mỗi API mỗi ngày + Cache 24h):
1. Google Trends Trending Now API (engine=google_trends_trending_now)
2. Google Autocomplete API (engine=google_autocomplete)
3. Google Search API (engine=google)
4. Google Trends API (engine=google_trends)
"""

import os
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, List, Any

import requests
from dotenv import load_dotenv

from backend.news_fetcher import detect_source_info

load_dotenv()

VN_TZ = timezone(timedelta(hours=7))
DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)


def get_api_key() -> str:
    load_dotenv(override=True)
    return os.getenv("SERPAPI_API_KEY", "").strip()


def get_serpapi_account_info() -> Dict[str, Any]:
    """Lấy thông tin số lượt tìm kiếm còn lại trên SerpApi (Miễn phí 100%, không trừ lượt)."""
    api_key = get_api_key()
    if not api_key:
        return {"status": "missing_key", "searches_left": 0, "searches_per_month": 250}

    try:
        resp = requests.get(
            "https://serpapi.com/account.json",
            params={"api_key": api_key},
            timeout=8
        )
        if resp.status_code == 200:
            data = resp.json()
            return {
                "status": data.get("account_status", "Active"),
                "plan_name": data.get("plan_name", "Free Plan"),
                "searches_left": data.get("total_searches_left", 0),
                "searches_per_month": data.get("searches_per_month", 250),
                "this_month_usage": data.get("this_month_usage", 0)
            }
    except Exception as e:
        return {"status": "error", "error": str(e), "searches_left": 0, "searches_per_month": 250}

    return {"status": "unknown", "searches_left": 0, "searches_per_month": 250}


def get_daily_serpapi_cache_path() -> Path:
    today_str = datetime.now(VN_TZ).strftime("%Y-%m-%d")
    return DATA_DIR / f"serpapi_daily_{today_str}.json"


def run_daily_4_serpapi_suite(candidate_keywords: List[str], force_refresh: bool = False) -> Dict[str, Any]:
    """
    Thực thi trọn gói đúng 1 lượt cho cả 4 con API của SerpApi trong ngày:
    - API 1: Google Trends Trending Now (geo=VN)
    - API 2: Google Autocomplete (cho keyword #1 ứng viên)
    - API 3: Google Search API (tìm bài viết mới 48h cho nhóm ứng viên hàng đầu)
    - API 4: Google Trends API (so sánh chỉ số quan tâm cho tối đa 5 ứng viên đầu)
    Nếu trong ngày đã gọi rồi và force_refresh=False thì đọc từ Cache để bảo vệ Quota.
    """
    cache_path = get_daily_serpapi_cache_path()
    if cache_path.exists() and not force_refresh:
        try:
            with open(cache_path, "r", encoding="utf-8") as f:
                cached = json.load(f)
                cached["from_cache"] = True
                return cached
        except Exception:
            pass

    api_key = get_api_key()
    result = {
        "date": datetime.now(VN_TZ).strftime("%Y-%m-%d %H:%M:%S"),
        "from_cache": False,
        "apis_called": {},
        "trending_now_items": [],
        "autocomplete_suggestions": [],
        "google_search_articles": [],
        "google_trends_scores": {}
    }

    if not api_key:
        return result

    top_5_candidates = [kw for kw in candidate_keywords[:5] if kw]
    top_1_keyword = top_5_candidates[0] if top_5_candidates else "Windows 11"

    # =========================================================================
    # 1. GOOGLE TRENDS TRENDING NOW API (1 lượt)
    # =========================================================================
    try:
        resp1 = requests.get(
            "https://serpapi.com/search.json",
            params={
                "engine": "google_trends_trending_now",
                "geo": "VN",
                "hl": "vi",
                "hours": "48",
                "api_key": api_key
            },
            timeout=15
        )
        if resp1.status_code == 200:
            data1 = resp1.json()
            trending_searches = data1.get("trending_searches", [])
            parsed_trends = []
            for item in trending_searches[:40]:
                query = item.get("query", "")
                if not query:
                    continue
                search_vol = item.get("search_volume", 0)
                increase_pct = item.get("increase_percentage", 0)
                categories = [c.get("name", "") for c in item.get("categories", []) if isinstance(c, dict)]
                breakdown = item.get("trend_breakdown", [])[:5]
                parsed_trends.append({
                    "query": query,
                    "search_volume": search_vol,
                    "increase_percentage": increase_pct,
                    "categories": categories,
                    "related_queries": breakdown
                })
            result["trending_now_items"] = parsed_trends
            result["apis_called"]["google_trends_trending_now"] = {
                "status": "success",
                "count": len(parsed_trends)
            }
        else:
            result["apis_called"]["google_trends_trending_now"] = {
                "status": f"http_{resp1.status_code}"
            }
    except Exception as e:
        result["apis_called"]["google_trends_trending_now"] = {"status": "error", "message": str(e)}

    # =========================================================================
    # 2. GOOGLE AUTOCOMPLETE API (1 lượt)
    # =========================================================================
    try:
        resp2 = requests.get(
            "https://serpapi.com/search.json",
            params={
                "engine": "google_autocomplete",
                "q": top_1_keyword,
                "gl": "vn",
                "hl": "vi",
                "api_key": api_key
            },
            timeout=12
        )
        if resp2.status_code == 200:
            data2 = resp2.json()
            suggestions = [
                s.get("value", "")
                for s in data2.get("suggestions", [])
                if s.get("value")
            ][:10]
            result["autocomplete_suggestions"] = suggestions
            result["apis_called"]["google_autocomplete"] = {
                "status": "success",
                "seed_query": top_1_keyword,
                "count": len(suggestions)
            }
        else:
            result["apis_called"]["google_autocomplete"] = {"status": f"http_{resp2.status_code}"}
    except Exception as e:
        result["apis_called"]["google_autocomplete"] = {"status": "error", "message": str(e)}

    # =========================================================================
    # 3. GOOGLE SEARCH API (1 lượt - tìm bài viết mới trong 48h cho cụm ứng viên)
    # =========================================================================
    try:
        search_terms = top_5_candidates[:3] if top_5_candidates else ["công nghệ mới", "AI", "Windows 11"]
        combined_query = " OR ".join([f'"{t}"' for t in search_terms])
        resp3 = requests.get(
            "https://serpapi.com/search.json",
            params={
                "engine": "google",
                "q": combined_query,
                "gl": "vn",
                "hl": "vi",
                "tbs": "qdr:d2",  # 48 giờ qua
                "num": 10,
                "api_key": api_key
            },
            timeout=15
        )
        if resp3.status_code == 200:
            data3 = resp3.json()
            organic = data3.get("organic_results", [])
            search_articles = []
            for item in organic:
                title = item.get("title", "")
                link = item.get("link", "")
                snippet = item.get("snippet", "")
                source = item.get("source", "") or "Google Search VN"
                date_str = item.get("date", "Mới cập nhật (trong 48h)")
                if not title or not link:
                    continue
                src_info = detect_source_info(source, link, "PRESS")
                search_articles.append({
                    "title": title,
                    "url": link,
                    "summary": snippet,
                    "source_name": src_info["name"],
                    "source_type": src_info["type"],
                    "source_badge": src_info["badge"],
                    "published_at": datetime.now(VN_TZ).isoformat(),
                    "hours_ago": 6.0,
                    "relative_time": date_str,
                    "within_24h": True,
                    "from_serpapi_search": True
                })
            result["google_search_articles"] = search_articles
            result["apis_called"]["google_search"] = {
                "status": "success",
                "query": combined_query,
                "count": len(search_articles)
            }
        else:
            result["apis_called"]["google_search"] = {"status": f"http_{resp3.status_code}"}
    except Exception as e:
        result["apis_called"]["google_search"] = {"status": "error", "message": str(e)}

    # =========================================================================
    # 4. GOOGLE TRENDS API (1 lượt - gộp tối đa 5 từ khóa cách nhau bởi dấu phẩy)
    # =========================================================================
    try:
        trends_q = ",".join(top_5_candidates) if top_5_candidates else "ChatGPT,Windows 11,GTA 6,VNeID,RTX 5090"
        resp4 = requests.get(
            "https://serpapi.com/search.json",
            params={
                "engine": "google_trends",
                "q": trends_q,
                "geo": "VN",
                "hl": "vi",
                "date": "now 7-d",
                "data_type": "TIMESERIES",
                "api_key": api_key
            },
            timeout=15
        )
        if resp4.status_code == 200:
            data4 = resp4.json()
            interest = data4.get("interest_over_time", {})
            averages = interest.get("averages", [])
            scores_map = {}
            for avg_item in averages:
                q_name = avg_item.get("query", "")
                val = avg_item.get("value", 0)
                if q_name:
                    scores_map[q_name.lower()] = val

            # Nếu averages không có sẵn, tính trung bình từ timeline_data
            if not scores_map and interest.get("timeline_data"):
                timeline = interest.get("timeline_data", [])[-10:]
                accum = {}
                counts = {}
                for point in timeline:
                    for v in point.get("values", []):
                        qn = (v.get("query") or "").lower()
                        ev = v.get("extracted_value", 0)
                        if qn:
                            accum[qn] = accum.get(qn, 0) + ev
                            counts[qn] = counts.get(qn, 0) + 1
                for qn, total_val in accum.items():
                    scores_map[qn] = round(total_val / max(1, counts[qn]))

            result["google_trends_scores"] = scores_map
            result["apis_called"]["google_trends"] = {
                "status": "success",
                "query": trends_q,
                "scores": scores_map
            }
        else:
            result["apis_called"]["google_trends"] = {"status": f"http_{resp4.status_code}"}
    except Exception as e:
        result["apis_called"]["google_trends"] = {"status": "error", "message": str(e)}

    # Lưu kết quả vào file Cache trong ngày
    try:
        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

    return result
