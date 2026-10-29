# -*- coding: utf-8 -*-
"""
Module thu thập tin tức công nghệ, phần mềm, game, chính sách số từ Báo chí VN & Đối thủ (trong 24h - 48h).
"""

import re
import time
import urllib.parse
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime
from typing import List, Dict, Optional
import concurrent.futures

import requests
import feedparser
from bs4 import BeautifulSoup

# Múi giờ Việt Nam (UTC+7)
VN_TZ = timezone(timedelta(hours=7))

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
)

# Danh sách nguồn RSS trực tiếp + Google News RSS chuyên biệt cho các trang Báo & Đối thủ
RSS_SOURCES = [
    # 1. NHÓM BÁO CÔNG NGHỆ & ĐỜI SỐNG SỐ
    {
        "name": "VnExpress Số Hóa",
        "url": "https://vnexpress.net/rss/so-hoa.rss",
        "source_type": "PRESS",
        "source_badge": "Báo chí",
        "domain": "vnexpress.net"
    },
    {
        "name": "GenK Công Nghệ",
        "url": "https://genk.vn/rss/home.rss",
        "source_type": "PRESS",
        "source_badge": "Báo chí",
        "domain": "genk.vn"
    },
    {
        "name": "Tinh Tế",
        "url": "https://tinhte.vn/rss",
        "source_type": "PRESS",
        "source_badge": "Cộng đồng / Báo",
        "domain": "tinhte.vn"
    },
    {
        "name": "Thanh Niên Công Nghệ",
        "url": "https://thanhnien.vn/rss/cong-nghe.rss",
        "source_type": "PRESS",
        "source_badge": "Báo chí",
        "domain": "thanhnien.vn"
    },
    {
        "name": "Tuổi Trẻ Công Nghệ",
        "url": "https://tuoitre.vn/rss/nhip-song-so.rss",
        "source_type": "PRESS",
        "source_badge": "Báo chí",
        "domain": "tuoitre.vn"
    },
    {
        "name": "Dân Trí Sức Mạnh Số",
        "url": "https://dantri.com.vn/rss/suc-manh-so.rss",
        "source_type": "PRESS",
        "source_badge": "Báo chí",
        "domain": "dantri.com.vn"
    },
    {
        "name": "GameK",
        "url": "https://gamek.vn/rss/home.rss",
        "source_type": "PRESS",
        "source_badge": "Báo Game",
        "domain": "gamek.vn"
    },

    # 2. NHÓM TRANG TIN ĐỐI THỦ CÙNG NGÀNH (Qua Google News RSS site:domain để luôn lấy chuẩn bài mới 48h)
    # max_items: số bài tối đa lấy từ 1 nguồn (mặc định 35). scraper: nguồn đọc thẳng HTML thay vì RSS.
    {
        "name": "CellphoneS (Sforum)",
        "url": "https://news.google.com/rss/search?q=site:cellphones.com.vn/sforum+when:2d&hl=vi&gl=VN&ceid=VN:vi",
        "source_type": "COMPETITOR",
        "source_badge": "Đối thủ",
        "domain": "cellphones.com.vn",
        "max_items": 80  # nguồn ưu tiên: lấy nhiều bài hơn các nguồn khác
    },
    {
        "name": "GearVN Blog",
        "url": "https://news.google.com/rss/search?q=site:gearvn.com/blogs+when:2d&hl=vi&gl=VN&ceid=VN:vi",
        "source_type": "COMPETITOR",
        "source_badge": "Đối thủ",
        "domain": "gearvn.com"
    },
    {
        "name": "Phong Vũ Công Nghệ",
        "url": "https://news.google.com/rss/search?q=site:phongvu.vn/cong-nghe+when:2d&hl=vi&gl=VN&ceid=VN:vi",
        "source_type": "COMPETITOR",
        "source_badge": "Đối thủ",
        "domain": "phongvu.vn"
    },
    {
        "name": "An Phát PC Tin Tức",
        "url": "https://www.anphatpc.com.vn/tin-tuc",
        "scraper": "anphat_html",  # Google News không lọc được /tin-tuc của An Phát nên đọc thẳng trang HTML
        "source_type": "COMPETITOR",
        "source_badge": "Đối thủ",
        "domain": "anphatpc.com.vn"
    },
    {
        "name": "FPT Shop Tin Tức",
        "url": "https://news.google.com/rss/search?q=site:fptshop.com.vn/tin-tuc+when:2d&hl=vi&gl=VN&ceid=VN:vi",
        "source_type": "COMPETITOR",
        "source_badge": "Đối thủ",
        "domain": "fptshop.com.vn"
    },
    {
        "name": "Thế Giới Di Động Tin Tức",
        "url": "https://news.google.com/rss/search?q=site:thegioididong.com/tin-tuc+when:2d&hl=vi&gl=VN&ceid=VN:vi",
        "source_type": "COMPETITOR",
        "source_badge": "Đối thủ",
        "domain": "thegioididong.com"
    },

    # 3. NHÓM CHỦ ĐỀ NGÁCH TRỌNG TÂM TRONG 48H QUA (Đảm bảo không bỏ sót ngách chiến lược của chị)
    {
        "name": "Tin AI & Phần mềm (Windows/Office)",
        "url": "https://news.google.com/rss/search?q=(Windows+11+OR+Office+OR+ChatGPT+OR+Gemini+OR+Claude+OR+AI+OR+DLSS+OR+RTX)+when:2d&hl=vi&gl=VN&ceid=VN:vi",
        "source_type": "PRESS",
        "source_badge": "Chuyên đề Tech",
        "domain": "google-news-tech"
    },
    {
        "name": "Tin Chính sách số & Mạng xã hội",
        "url": "https://news.google.com/rss/search?q=(VNeID+OR+%22m%E1%BA%A1ng+x%C3%A3+h%E1%BB%99i%22+OR+Facebook+OR+YouTube+OR+TikTok+OR+Zalo+OR+%22v%E1%BA%ADt+ph%E1%BA%A9m+%E1%BA%A3o%22+OR+%22m%C3%A3+%C4%91%E1%BB%99c%22)+when:2d&hl=vi&gl=VN&ceid=VN:vi",
        "source_type": "PRESS",
        "source_badge": "Chính sách / MXH",
        "domain": "google-news-policy"
    },
    {
        "name": "Tin Làng Game & Cấu hình PC",
        "url": "https://news.google.com/rss/search?q=(%22GTA+6%22+OR+Steam+OR+%22game+m%E1%BB%9Bi%22+OR+LMHT+OR+Valorant+OR+PlayStation+OR+%22card+%C4%91%E1%BB%93+h%E1%BB%8Da%22)+when:2d&hl=vi&gl=VN&ceid=VN:vi",
        "source_type": "PRESS",
        "source_badge": "Tin Game / PC",
        "domain": "google-news-game"
    }
]

# Danh sách tên domain đối thủ để nhận diện tự động khi bài viết đến từ Google News hoặc SerpApi
COMPETITOR_KEYWORDS_IN_SOURCE = [
    "sforum", "cellphones", "gearvn", "phong vũ", "phongvu",
    "hacom", "hanoicomputer", "an phát", "anphat", "thinkpro",
    "fpt shop", "fptshop", "thế giới di động", "thegioididong",
    "hoàng hà", "hoanghamobile", "di động việt", "didongviet",
    "tnc store", "tncstore", "xgear", "memoryzone", "hotgear"
]


def detect_source_info(raw_source_name: str, url: str, default_type: str = "PRESS") -> Dict[str, str]:
    """Nhận diện chính xác tên nguồn và phân loại Báo chí vs Đối thủ."""
    combined = f"{raw_source_name} {url}".lower()
    for comp in COMPETITOR_KEYWORDS_IN_SOURCE:
        if comp in combined:
            # Chuẩn hóa tên đối thủ đẹp mắt
            if "sforum" in combined or "cellphones" in combined:
                return {"name": "CellphoneS (Sforum)", "type": "COMPETITOR", "badge": "Đối thủ"}
            if "gearvn" in combined:
                return {"name": "GearVN", "type": "COMPETITOR", "badge": "Đối thủ"}
            if "phongvu" in combined or "phong vũ" in combined:
                return {"name": "Phong Vũ", "type": "COMPETITOR", "badge": "Đối thủ"}
            if "fpt" in combined:
                return {"name": "FPT Shop", "type": "COMPETITOR", "badge": "Đối thủ"}
            if "thegioididong" in combined or "thế giới di động" in combined:
                return {"name": "Thế Giới Di Động", "type": "COMPETITOR", "badge": "Đối thủ"}
            if "thinkpro" in combined:
                return {"name": "ThinkPro", "type": "COMPETITOR", "badge": "Đối thủ"}
            if "anphat" in combined or "an phát" in combined:
                return {"name": "An Phát PC", "type": "COMPETITOR", "badge": "Đối thủ"}
            if "hacom" in combined or "hanoicomputer" in combined:
                return {"name": "HACOM", "type": "COMPETITOR", "badge": "Đối thủ"}
            if "memoryzone" in combined:
                return {"name": "MemoryZone", "type": "COMPETITOR", "badge": "Đối thủ"}
            if "tnc" in combined:
                return {"name": "TNC Store", "type": "COMPETITOR", "badge": "TNC Store"}
            return {"name": raw_source_name or "Trang Đối Thủ", "type": "COMPETITOR", "badge": "Đối thủ"}

    # Báo chí lớn
    if "vnexpress" in combined:
        return {"name": "VnExpress Số Hóa", "type": "PRESS", "badge": "Báo chí"}
    if "genk" in combined:
        return {"name": "GenK", "type": "PRESS", "badge": "Báo chí"}
    if "tinhte" in combined or "tinh tế" in combined:
        return {"name": "Tinh Tế", "type": "PRESS", "badge": "Báo chí"}
    if "gamek" in combined:
        return {"name": "GameK", "type": "PRESS", "badge": "Báo Game"}
    if "thanhnien" in combined or "thanh niên" in combined:
        return {"name": "Báo Thanh Niên", "type": "PRESS", "badge": "Báo chí"}
    if "tuoitre" in combined or "tuổi trẻ" in combined:
        return {"name": "Báo Tuổi Trẻ", "type": "PRESS", "badge": "Báo chí"}
    if "dantri" in combined or "dân trí" in combined:
        return {"name": "Báo Dân Trí", "type": "PRESS", "badge": "Báo chí"}
    if "24h.com.vn" in combined:
        return {"name": "24h Công Nghệ", "type": "PRESS", "badge": "Báo chí"}
    if "vietnamnet" in combined:
        return {"name": "VietNamNet", "type": "PRESS", "badge": "Báo chí"}
    if "vtv" in combined:
        return {"name": "VTV Công Nghệ", "type": "PRESS", "badge": "Báo chí"}

    badge = "Đối thủ" if default_type == "COMPETITOR" else "Báo chí"
    return {"name": raw_source_name, "type": default_type, "badge": badge}


def clean_html_summary(raw_html: str) -> str:
    """Làm sạch thẻ HTML trong phần mô tả RSS."""
    if not raw_html:
        return ""
    soup = BeautifulSoup(raw_html, "html.parser")
    text = soup.get_text(separator=" ", strip=True)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:260] + ("..." if len(text) > 260 else "")


def parse_pub_date(entry) -> datetime:
    """Chuyển đổi thời gian xuất bản của bài viết về múi giờ VN."""
    now_vn = datetime.now(VN_TZ)
    for attr in ("published", "updated", "pubDate"):
        val = entry.get(attr)
        if val:
            try:
                dt = parsedate_to_datetime(val)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=VN_TZ)
                else:
                    dt = dt.astimezone(VN_TZ)
                # Nếu thời gian lớn hơn hiện tại do lệch múi giờ server, gán về hiện tại
                if dt > now_vn + timedelta(minutes=10):
                    return now_vn
                return dt
            except Exception:
                pass

    if getattr(entry, "published_parsed", None):
        try:
            ts = time.mktime(entry.published_parsed)
            dt = datetime.fromtimestamp(ts, tz=VN_TZ)
            return dt
        except Exception:
            pass

    return now_vn - timedelta(hours=3)


def format_relative_time(dt: datetime, now_vn: datetime) -> str:
    """Hiển thị thời gian tương đối dễ đọc (VD: '2 giờ trước', '26 giờ trước')."""
    diff = now_vn - dt
    hours = max(0.1, diff.total_seconds() / 3600.0)
    if hours < 1:
        mins = max(1, int(diff.total_seconds() / 60))
        return f"{mins} phút trước"
    elif hours < 48:
        return f"{int(hours)} giờ trước"
    else:
        days = int(hours / 24)
        return f"{days} ngày trước"


def parse_anphat_time(text: str, now_vn: datetime) -> Optional[datetime]:
    """Đọc ngày giờ trên trang tin An Phát: 'Hôm nay, 11:45 am', 'Hôm qua, 9:18 pm', '17-10-2026, 9:18 am'."""
    t = re.sub(r"\s+", " ", text or "").strip().lower()
    m = re.search(r"(\d{1,2}):(\d{2})\s*(am|pm)?", t)
    if not m:
        return None
    hour, minute = int(m.group(1)), int(m.group(2))
    if m.group(3) == "pm" and hour < 12:
        hour += 12
    elif m.group(3) == "am" and hour == 12:
        hour = 0
    if "hôm nay" in t:
        day = now_vn
    elif "hôm qua" in t:
        day = now_vn - timedelta(days=1)
    else:
        d = re.search(r"(\d{1,2})-(\d{1,2})-(\d{4})", t)
        if not d:
            return None
        try:
            day = datetime(int(d.group(3)), int(d.group(2)), int(d.group(1)), tzinfo=VN_TZ)
        except ValueError:
            return None
    return day.replace(hour=hour, minute=minute, second=0, microsecond=0)


def fetch_anphat_articles(source_cfg: Dict, max_hours: int = 48) -> List[Dict]:
    """Đọc thẳng https://www.anphatpc.com.vn/tin-tuc (mỗi bài có thẻ <time> kèm ngày giờ đăng)."""
    articles = []
    now_vn = datetime.now(VN_TZ)
    cutoff = now_vn - timedelta(hours=max_hours)
    base = "https://www.anphatpc.com.vn"
    try:
        resp = requests.get(source_cfg["url"], headers={"User-Agent": USER_AGENT}, timeout=15)
        if resp.status_code != 200:
            return []
        soup = BeautifulSoup(resp.text, "html.parser")
        seen = set()
        for tm in soup.find_all("time"):
            pub_dt = parse_anphat_time(tm.get_text(" ", strip=True), now_vn)
            if not pub_dt or pub_dt > now_vn + timedelta(minutes=10) or pub_dt < cutoff:
                continue
            # Tìm link tiêu đề trong khối chứa thẻ <time>
            link_tag, node = None, tm.parent
            for _ in range(4):
                if node is None:
                    break
                # Link tiêu đề = link .html có chữ dài nhất, bỏ link tên tác giả (nằm trong thẻ class "b-author")
                links = [a for a in node.find_all("a", href=True)
                         if a["href"].endswith(".html") and a.get_text(strip=True)
                         and not a.find_parent(class_=re.compile("author", re.I))]
                if links:
                    link_tag = max(links, key=lambda a: len(a.get_text(strip=True)))
                    break
                node = node.parent
            if not link_tag:
                continue
            title = re.sub(r"\s+", " ", link_tag.get_text(" ", strip=True)).strip()
            url = urllib.parse.urljoin(base, link_tag["href"])
            if not title or url in seen:
                continue
            seen.add(url)
            desc = node.find("p") if node else None
            summary = clean_html_summary(desc.get_text(" ", strip=True)) if desc else ""
            src_info = detect_source_info(source_cfg["name"], url, source_cfg["source_type"])
            hours_ago = max(0.1, (now_vn - pub_dt).total_seconds() / 3600.0)
            articles.append({
                "title": title,
                "url": url,
                "summary": summary if summary and summary != title else "",
                "source_name": src_info["name"],
                "source_type": src_info["type"],
                "source_badge": src_info["badge"],
                "published_at": pub_dt.isoformat(),
                "hours_ago": round(hours_ago, 1),
                "relative_time": format_relative_time(pub_dt, now_vn),
                "within_24h": hours_ago <= 24.0
            })
    except Exception:
        pass
    return articles


def fetch_single_feed(source_cfg: Dict, max_hours: int = 48) -> List[Dict]:
    """Tải và phân tích 1 nguồn RSS trong khoảng thời gian max_hours (mặc định 48h)."""
    if source_cfg.get("scraper") == "anphat_html":
        return fetch_anphat_articles(source_cfg, max_hours)
    articles = []
    now_vn = datetime.now(VN_TZ)
    cutoff = now_vn - timedelta(hours=max_hours)

    try:
        resp = requests.get(
            source_cfg["url"],
            headers={"User-Agent": USER_AGENT},
            timeout=10
        )
        if resp.status_code != 200:
            return []

        feed = feedparser.parse(resp.content)
        for entry in feed.entries[:source_cfg.get("max_items", 35)]:
            import html as _html
            title = _html.unescape(entry.get("title") or "").strip()
            link = (entry.get("link") or "").strip()
            if not title or not link:
                continue

            # Nếu là Google News RSS, tiêu đề thường có dạng "Tiêu đề bài viết - Tên Báo"
            extracted_publisher = source_cfg["name"]
            if " - " in title and "news.google.com" in source_cfg["url"]:
                parts = title.rsplit(" - ", 1)
                if len(parts) == 2 and len(parts[1]) < 35:
                    title = parts[0].strip()
                    extracted_publisher = parts[1].strip()

            pub_dt = parse_pub_date(entry)
            if pub_dt < cutoff:
                continue

            hours_ago = max(0.1, (now_vn - pub_dt).total_seconds() / 3600.0)
            summary = clean_html_summary(entry.get("summary") or entry.get("description") or "")

            src_info = detect_source_info(extracted_publisher, link, source_cfg["source_type"])

            articles.append({
                "title": title,
                "url": link,
                "summary": summary if summary and summary != title else "",
                "source_name": src_info["name"],
                "source_type": src_info["type"],  # PRESS hoặc COMPETITOR
                "source_badge": src_info["badge"],
                "published_at": pub_dt.isoformat(),
                "hours_ago": round(hours_ago, 1),
                "relative_time": format_relative_time(pub_dt, now_vn),
                "within_24h": hours_ago <= 24.0
            })
    except Exception:
        pass

    return articles


def fetch_all_rss_articles(max_hours: int = 48) -> List[Dict]:
    """Quét song song tất cả các nguồn RSS và khử trùng lặp bài viết."""
    all_raw = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
        futures = [executor.submit(fetch_single_feed, src, max_hours) for src in RSS_SOURCES]
        for fut in concurrent.futures.as_completed(futures):
            try:
                all_raw.extend(fut.result())
            except Exception:
                pass

    # Khử trùng lặp theo tiêu đề chuẩn hóa hoặc URL
    seen_titles = set()
    unique_articles = []
    # Ưu tiên bài mới nhất lên đầu
    all_raw.sort(key=lambda x: x["hours_ago"])

    for art in all_raw:
        norm_title = re.sub(r"\W+", "", art["title"].lower())[:60]
        if norm_title in seen_titles:
            continue
        seen_titles.add(norm_title)
        unique_articles.append(art)

    return unique_articles
