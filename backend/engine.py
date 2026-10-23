# -*- coding: utf-8 -*-
"""
Module điều phối trung tâm (Engine):
- Bước 1: Quét tin tức từ Báo công nghệ VN & Đối thủ (trong 24h - 48h).
- Bước 2: Phân loại 9 Ngách Nội Dung & Trích xuất/Gom cụm Keyword.
- Bước 3: Gọi trọn gói 4 cổng SerpApi (1 lượt/con/ngày, có Cache 24h) để làm giàu dữ liệu và chấm điểm.
- Bước 4: Chấm điểm & Chọn ra Top 20 Keyword điểm cao nhất bất kỳ.
- Bước 5: Tuyển chọn Top 5 bài viết mới nhất (ưu tiên đa dạng nguồn Báo + Đối thủ) cho mỗi Keyword.
- Lưu ý: tên khóa JSON "top_10_keywords" / "top_3_articles" được giữ nguyên để tương thích báo cáo cũ,
  nhưng nay chứa TOP_KEYWORDS (20) keyword và TOP_ARTICLES (5) bài viết.
"""

import json
import re
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, List, Any

from backend.classifier import (
    NICHES,
    is_promo_noise,
    is_smartphone_topic,
    classify_niche,
    extract_core_keyword
)
from backend.news_fetcher import fetch_all_rss_articles
from backend.serpapi_client import (
    run_daily_4_serpapi_suite,
    get_serpapi_account_info,
    DATA_DIR
)
from backend.seo_suggester import suggest_seo_keywords

VN_TZ = timezone(timedelta(hours=7))

TOP_KEYWORDS = 20    # số keyword đưa vào báo cáo mỗi ngày
TOP_ARTICLES = 5     # số bài viết đại diện cho mỗi keyword
SEO_SUGGESTIONS = 3  # số keyword gợi ý viết bài SEO cho mỗi keyword


GENERIC_TOKENS = {
    "mới", "nhất", "cập", "nhật", "tính", "năng", "cách", "lỗi", "giá", "tin", "tức",
    "của", "cho", "các", "một", "những", "với", "trên", "được", "này", "new", "the", "and",
}


def _tokens(text: str) -> List[str]:
    return [t for t in re.split(r"\W+", text.lower()) if len(t) >= 3 and t not in GENERIC_TOKENS]


def phrase_in(needle: str, haystack: str) -> bool:
    """Cụm `needle` xuất hiện nguyên vẹn (theo ranh giới từ) trong `haystack`."""
    needle, haystack = needle.strip().lower(), haystack.lower()
    if not needle:
        return False
    return re.search(r"(?<!\w)" + re.escape(needle) + r"(?!\w)", haystack) is not None


def keywords_match(a: str, b: str) -> bool:
    """Hai cụm từ khóa được coi là cùng chủ đề khi: cụm này chứa nguyên cụm kia,
    hoặc chia sẻ >= 2 từ đặc trưng (hoặc toàn bộ từ đặc trưng nếu cụm chỉ có 1 từ)."""
    if phrase_in(a, b) or phrase_in(b, a):
        return True
    ta, tb = set(_tokens(a)), set(_tokens(b))
    if not ta or not tb:
        return False
    common = ta & tb
    return len(common) >= 2 or (len(common) >= 1 and min(len(ta), len(tb)) == 1)


def select_top_articles(articles: List[Dict], all_pool: List[Dict], keyword: str, limit: int = TOP_ARTICLES) -> List[Dict]:
    """
    Chọn ra đúng Top `limit` bài viết tốt nhất cho 1 Keyword trong vòng 24h - 48h:
    - Ưu tiên bài viết mới nhất (24h đầu tiên, mở rộng 48h).
    - Ưu tiên đa dạng nguồn (không lấy trùng nguồn nếu có nhiều nguồn khác nhau cùng viết).
    - Nếu cụm hiện tại có ít hơn `limit` bài, tìm thêm trong kho bài viết 48h có chứa từ khóa liên quan.
    """
    # Sắp xếp ưu tiên bài trong 24h và số giờ nhỏ nhất
    sorted_arts = sorted(
        articles,
        key=lambda x: (0 if x.get("within_24h", True) else 1, x.get("hours_ago", 12.0))
    )

    selected = []
    used_urls = set()
    used_sources = set()

    # Lượt 1: Ưu tiên mỗi nguồn 1 bài mới nhất để đa dạng góc nhìn (Báo chí + Đối thủ)
    for art in sorted_arts:
        if len(selected) >= limit:
            break
        src_name = art.get("source_name", "")
        url = art.get("url", "")
        if url not in used_urls and src_name not in used_sources:
            selected.append(art)
            used_urls.add(url)
            used_sources.add(src_name)

    # Lượt 2: Nếu chưa đủ bài, lấy tiếp các bài mới nhất trong cùng cụm
    for art in sorted_arts:
        if len(selected) >= limit:
            break
        url = art.get("url", "")
        if url not in used_urls:
            selected.append(art)
            used_urls.add(url)

    # Lượt 3: Nếu vẫn chưa đủ bài, tìm mở rộng trong toàn bộ kho bài viết 48h theo từ khóa con
    if len(selected) < limit:
        kw_tokens = _tokens(keyword)
        for art in all_pool:
            if len(selected) >= limit:
                break
            url = art.get("url", "")
            if url in used_urls:
                continue
            title_l = art.get("title", "").lower()
            if kw_tokens and any(tok in title_l for tok in kw_tokens):
                selected.append(art)
                used_urls.add(url)

    return selected[:limit]


def generate_related_keywords(core_kw: str, articles: List[Dict], serp_data: Dict) -> List[str]:
    """Tạo danh sách từ khóa phụ / gợi ý tìm kiếm (Long-tail keywords) cho Keyword chính."""
    related = []
    core_lower = core_kw.lower()

    # 1. Lấy từ Google Autocomplete nếu khớp
    for sug in serp_data.get("autocomplete_suggestions", []):
        if sug.lower() != core_lower and (core_lower in sug.lower() or any(w in sug.lower() for w in core_lower.split()[:2])):
            related.append(sug)

    # 2. Lấy từ Google Trends Trending Now breakdown nếu khớp
    for tr in serp_data.get("trending_now_items", []):
        q = tr.get("query", "")
        if q.lower() in core_lower or core_lower in q.lower():
            for rq in tr.get("related_queries", []):
                if rq not in related and rq.lower() != core_lower:
                    related.append(rq)

    # 3. Sinh từ khóa SEO thực chiến theo ngữ cảnh bài viết
    titles_joined = " ".join(a.get("title", "").lower() for a in articles)
    if "cấu hình" in titles_joined and f"cấu hình {core_kw}" not in [r.lower() for r in related]:
        related.append(f"cấu hình {core_kw}")
    if ("lỗi" in titles_joined or "khắc phục" in titles_joined):
        related.append(f"cách sửa lỗi {core_kw}")
    if ("ra mắt" in titles_joined or "mới" in titles_joined):
        related.append(f"{core_kw} có gì mới")
    if ("cách" in titles_joined or "hướng dẫn" in titles_joined):
        related.append(f"hướng dẫn {core_kw}")
    if "giá" in titles_joined:
        related.append(f"giá {core_kw} chính hãng")

    # Đảm bảo luôn có ít nhất 3 gợi ý từ khóa phụ hữu ích cho SEO
    defaults = [
        f"{core_kw} mới nhất",
        f"đánh giá {core_kw}",
        f"tin tức {core_kw}"
    ]
    for d in defaults:
        if len(related) >= 4:
            break
        if d.lower() not in [r.lower() for r in related]:
            related.append(d)

    return related[:5]


def build_daily_top10_report(max_hours: int = 48, force_serpapi: bool = False) -> Dict[str, Any]:
    """
    Chạy toàn bộ quy trình nghiên cứu Top 20 Keyword + Top 5 bài viết mỗi keyword.
    """
    now_vn = datetime.now(VN_TZ)

    # BƯỚC 1: Quét toàn bộ bài viết từ Báo công nghệ & Đối thủ trong 48h qua
    raw_articles = fetch_all_rss_articles(max_hours=max_hours)

    # BƯỚC 2: Lọc nhiễu + Lọc bỏ chủ đề điện thoại di động (smartphone), phân loại 9 Ngách và trích xuất cụm Keyword
    clusters: Dict[str, Dict[str, Any]] = {}
    clean_pool = []

    for art in raw_articles:
        title = art.get("title", "")
        summary = art.get("summary", "")
        if is_promo_noise(title) or is_smartphone_topic(title, summary):
            continue

        niche = classify_niche(title, summary)
        cluster_id, display_kw = extract_core_keyword(title, summary)
        if is_smartphone_topic(display_kw):
            continue

        art["niche"] = niche
        art["extracted_keyword"] = display_kw
        clean_pool.append(art)

        if cluster_id not in clusters:
            clusters[cluster_id] = {
                "cluster_id": cluster_id,
                "keyword": display_kw,
                "niche": niche,
                "articles": [],
                "press_sources": set(),
                "competitor_sources": set(),
                "has_24h_article": False,
                "min_hours_ago": 99.0
            }

        cl = clusters[cluster_id]
        cl["articles"].append(art)
        if art["source_type"] == "COMPETITOR":
            cl["competitor_sources"].add(art["source_name"])
        else:
            cl["press_sources"].add(art["source_name"])

        if art.get("within_24h", False):
            cl["has_24h_article"] = True
        if art.get("hours_ago", 48.0) < cl["min_hours_ago"]:
            cl["min_hours_ago"] = art.get("hours_ago", 48.0)

    # Sắp xếp sơ bộ để chọn ra Top 5 ứng viên gửi vào 4 cổng SerpApi
    prelim_list = sorted(
        clusters.values(),
        key=lambda c: (
            len(c["press_sources"]) + len(c["competitor_sources"]) * 1.5,
            len(c["articles"]),
            -c["min_hours_ago"]
        ),
        reverse=True
    )
    candidate_keywords = [c["keyword"] for c in prelim_list[:5]]

    # BƯỚC 3: Tự động gọi trọn gói 4 cổng SerpApi (1 lượt/con/ngày + Cache 24h)
    serp_data = run_daily_4_serpapi_suite(
        candidate_keywords=candidate_keywords,
        force_refresh=force_serpapi
    )

    # Bổ sung thêm các bài viết mới thu được từ Google Search API (SerpApi) vào cụm tương ứng
    for s_art in serp_data.get("google_search_articles", []):
        title = s_art.get("title", "")
        summary = s_art.get("summary", "")
        if is_promo_noise(title) or is_smartphone_topic(title, summary):
            continue
        niche = classify_niche(title, summary)
        cluster_id, display_kw = extract_core_keyword(title, summary)
        if is_smartphone_topic(display_kw):
            continue
        s_art["niche"] = niche
        clean_pool.append(s_art)

        # Kiểm tra xem có khớp với cụm sẵn có nào không
        matched_cid = None
        for cid, cl in clusters.items():
            if phrase_in(cid, title) or phrase_in(cl["keyword"], title):
                matched_cid = cid
                break
        target_cid = matched_cid or cluster_id
        if target_cid not in clusters:
            clusters[target_cid] = {
                "cluster_id": target_cid,
                "keyword": display_kw,
                "niche": niche,
                "articles": [],
                "press_sources": set(),
                "competitor_sources": set(),
                "has_24h_article": False,
                "min_hours_ago": 99.0
            }
        tcl = clusters[target_cid]
        tcl["articles"].append(s_art)
        if s_art.get("within_24h", False):
            tcl["has_24h_article"] = True
        tcl["min_hours_ago"] = min(tcl["min_hours_ago"], s_art.get("hours_ago", 48.0))
        if s_art["source_type"] == "COMPETITOR":
            clusters[target_cid]["competitor_sources"].add(s_art["source_name"])
        else:
            clusters[target_cid]["press_sources"].add(s_art["source_name"])

    # BƯỚC 4: Chấm điểm từng cụm Keyword theo đúng Công thức 4 tiêu chí (Thang 100 điểm)
    trending_now_queries = [
        t.get("query", "").lower() for t in serp_data.get("trending_now_items", [])
    ]
    gtrends_scores = serp_data.get("google_trends_scores", {})

    scored_clusters = []
    for cid, cl in clusters.items():
        num_articles = len(cl["articles"])
        num_press = len(cl["press_sources"])
        num_comp = len(cl["competitor_sources"])
        total_unique_sources = num_press + num_comp

        # 1. Độ phủ đa nguồn (Tối đa 40 điểm)
        coverage_score = min(40.0, total_unique_sources * 9.0 + num_articles * 2.5)
        if num_press >= 1 and num_comp >= 1:
            coverage_score = min(40.0, coverage_score + 6.0)  # Thưởng khi cả Báo & Đối thủ cùng viết

        # 2. Hành động của Đối thủ (Tối đa 25 điểm)
        if num_comp >= 2:
            competitor_score = 25.0
        elif num_comp == 1:
            competitor_score = 18.0
        else:
            # Nếu đối thủ chưa kịp viết nhưng nhiều báo đang viết -> Cơ hội đi trước đối thủ
            competitor_score = min(14.0, num_press * 4.5)

        # 3. Độ tươi mới 24h/48h (Tối đa 20 điểm)
        min_h = cl["min_hours_ago"]
        if min_h <= 6:
            freshness_score = 20.0
        elif min_h <= 24:
            freshness_score = 17.5
        else:
            freshness_score = 13.0  # Trong khung 24h - 48h

        # 4. Tín hiệu 4 cổng SerpApi (Tối đa 15 điểm)
        serp_score = 5.0  # Điểm nền
        kw_lower = cl["keyword"].lower()
        # Kiểm tra khớp với Google Trends Trending Now
        is_trending_now = False
        for tq in trending_now_queries:
            if tq and keywords_match(tq, kw_lower):
                serp_score += 6.0
                is_trending_now = True
                break

        # Kiểm tra điểm Google Trends Timeseries
        gt_val = 0
        for g_k, g_v in gtrends_scores.items():
            if keywords_match(g_k, kw_lower):
                gt_val = g_v
                serp_score += min(5.0, (g_v / 100.0) * 6.0)
                break

        serp_score = min(15.0, serp_score)

        total_score = round(coverage_score + competitor_score + freshness_score + serp_score, 1)
        total_score = min(99.5, total_score)

        # Tuyển chọn Top 5 bài viết đại diện tốt nhất (biến giữ tên top_3_arts để khớp khóa JSON cũ)
        top_3_arts = select_top_articles(cl["articles"], clean_pool, cl["keyword"])

        # Chỉ xét những keyword có bài viết thực tế
        if not top_3_arts:
            continue

        # Sinh Gợi ý Keyword viết bài SEO (cụm ngắn, chính xác) bám sát vấn đề của các bài viết top
        seo_suggestions = suggest_seo_keywords(
            keyword=cl["keyword"],
            cluster_id=cid,
            articles=top_3_arts,
            limit=SEO_SUGGESTIONS,
            autocomplete=serp_data.get("autocomplete_suggestions", [])
        )
        related_kws = [s["keyword"] for s in seo_suggestions] if seo_suggestions else generate_related_keywords(cl["keyword"], top_3_arts, serp_data)

        scored_clusters.append({
            "keyword": cl["keyword"],
            "cluster_id": cid,
            "niche": cl["niche"],
            "total_score": total_score,
            "score_breakdown": {
                "coverage": round(coverage_score, 1),
                "competitor": round(competitor_score, 1),
                "freshness": round(freshness_score, 1),
                "serpapi_trend": round(serp_score, 1)
            },
            "stats": {
                "total_articles_found": num_articles,
                "press_count": num_press,
                "competitor_count": num_comp,
                "press_list": sorted(list(cl["press_sources"])),
                "competitor_list": sorted(list(cl["competitor_sources"])),
                "newest_hours_ago": round(min_h, 1),
                "is_trending_now": is_trending_now,
                "google_trends_index": gt_val
            },
            "seo_suggested_keywords": seo_suggestions,
            "related_keywords": related_kws,
            "top_3_articles": top_3_arts
        })

    # Sắp xếp lấy đúng Top 20 Keyword điểm cao nhất bất kỳ
    scored_clusters.sort(
        key=lambda x: (x["total_score"], len(x["top_3_articles"]), -x["stats"]["newest_hours_ago"]),
        reverse=True
    )

    top_10 = []
    for idx, item in enumerate(scored_clusters[:TOP_KEYWORDS], start=1):
        item["rank"] = idx
        top_10.append(item)

    account_info = get_serpapi_account_info()

    report = {
        "generated_at": now_vn.strftime("%d/%m/%Y %H:%M:%S"),
        "time_window_hours": max_hours,
        "total_articles_scanned": len(raw_articles),
        "total_clusters_detected": len(scored_clusters),
        "serpapi_status": {
            "account": account_info,
            "daily_suite_from_cache": serp_data.get("from_cache", False),
            "apis_called": serp_data.get("apis_called", {}),
            "trending_now_highlights": serp_data.get("trending_now_items", [])[:12],
            "autocomplete_highlights": serp_data.get("autocomplete_suggestions", [])[:8]
        },
        "niches_catalog": list(NICHES.values()),
        "top_10_keywords": top_10
    }

    # Lưu kết quả báo cáo mới nhất ra file JSON
    latest_report_path = DATA_DIR / "latest_top10_report.json"
    try:
        with open(latest_report_path, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[engine] Không ghi được {latest_report_path.name}: {e}")

    return report
