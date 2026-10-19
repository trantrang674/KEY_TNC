# -*- coding: utf-8 -*-
"""
Gợi ý KEYWORD VIẾT BÀI SEO cho website, bám đúng "góc vấn đề" mà Top 3 bài viết đang đề cập.

Luồng chuẩn:
Keyword thu thập -> Top 3 bài viết -> Gợi ý Keyword sẽ dùng để viết bài SEO cho website.
Ví dụ:
- Keyword thu thập: "Windows 11"
  + Bài viết: "Windows 11 kết nối sâu hơn với điện thoại, chuyển tệp dễ dàng"
  -> Gợi ý Keyword SEO: "Windows 11 kết nối sâu hơn với điện thoại", "Cách kết nối Windows 11 với điện thoại chuyển tệp"
"""

import html
import re
from typing import Dict, List

from backend.classifier import KNOWN_TECH_ENTITIES

# Danh sách các từ nối/hư từ ở đầu hoặc cuối cụm cần gọt sạch để tạo thành Keyword hoàn chỉnh
LEADING_NOISE_WORDS = {
    "của", "về", "và", "với", "khi", "được", "bị", "cho", "từ", "trong", "trên",
    "những", "các", "một", "này", "kia", "đó", "đây", "vừa", "đã", "đang", "sẽ",
    "hàng", "kết", "gì", "cần", "biết", "thêm", "từng", "có", "rằng", "là"
}

TRAILING_NOISE_WORDS = {
    "và", "để", "với", "của", "là", "thì", "mà", "cho", "khi", "nhưng", "hay",
    "hoặc", "ở", "tại", "đã", "sẽ", "đang", "bị", "được", "có", "những", "các",
    "một", "này", "nào", "vừa", "cũng", "chú", "người", "nội", "thư", "mỗi",
    "như", "tới", "đến", "trước", "sau", "vào", "ra"
}

GENERIC_TOKENS = {
    "tin", "tức", "mới", "nhất", "cập", "nhật", "tính", "năng", "nền", "tảng",
    "xu", "hướng", "cảnh", "báo", "bảo", "mật", "ứng", "dụng", "công", "nghệ"
}


def clean_article_title(title: str) -> str:
    """Giải mã HTML entities (VD: T&iacute;nh -> Tính) và làm sạch tiêu đề."""
    t = html.unescape(title or "")
    # Bỏ hậu tố tên báo ở cuối nếu có
    t = re.sub(r"\s+[-|–—]\s+[^-|–—]{2,35}$", "", t)
    # Bỏ cụm ( YOUTUBE LIVE ) hoặc [Trực tiếp] ở đầu
    t = re.sub(r"^\s*[\(\[][^)\]]*live[^)\]]*[\)\]]\s*", "", t, flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", t).strip()


def is_product_sku_or_live_noise(raw_title: str) -> bool:
    """Nhận diện tiêu đề là mã SKU sản phẩm, livestream bóng đá hoặc tiêu đề bị cắt cụt '...'."""
    if raw_title.count("/") >= 3:
        return True
    t_lower = raw_title.lower()
    if "youtube live" in t_lower or ("vs " in t_lower and "live" in t_lower):
        return True
    # Tiêu đề bị cắt cụt bằng dấu ... ở cuối hoặc toàn chữ in hoa
    if raw_title.strip().endswith("...") or raw_title.strip().endswith("…"):
        return True
    letters = [c for c in raw_title if c.isalpha()]
    if letters and (sum(c.isupper() for c in letters) / len(letters) > 0.7):
        return True
    return False


def _detect_intent_label(text: str) -> str:
    low = text.lower()
    if re.search(r"cách |hướng dẫn|thủ thuật|mẹo|làm sao", low):
        return "Keyword Hướng dẫn / Thủ thuật"
    if re.search(r"lỗi|khắc phục|sửa|màn hình xanh|tụt fps", low):
        return "Keyword Khắc phục lỗi"
    if re.search(r"miễn phí|tặng game|nhận ngay|free", low):
        return "Keyword Săn ưu đãi / Game miễn phí"
    if re.search(r"liên kết|xác thực|bắt buộc|quy định|nghị định", low):
        return "Keyword Chính sách / Hướng dẫn thực hiện"
    if re.search(r"cấu hình|thông số|benchmark|hiệu năng", low):
        return "Keyword Cấu hình / Đánh giá"
    if re.search(r"kết nối|tính năng|cập nhật|ra mắt|trailer", low):
        return "Keyword Tính năng / Tin mới"
    if re.search(r"mã độc|tống tiền|lừa đảo|bảo mật|lỗ hổng", low):
        return "Keyword Cảnh báo & Phòng tránh"
    return "Keyword Tin tức SEO trọng tâm"


def _synthesize_problem_keyword(raw_title: str, core_entity: str) -> List[str]:
    """
    Phân tích ngữ nghĩa tiêu đề bài viết để rút ra đúng các 'Keyword vấn đề' chuẩn SEO.
    """
    if not raw_title or is_product_sku_or_live_noise(raw_title):
        return []

    t = clean_article_title(raw_title)
    t_lower = t.lower()
    core_lower = core_entity.lower()

    # -----------------------------------------------------------------------
    # 1. CÁC MẪU NGỮ NGHĨA ĐẶC THÙ THEO GÓC VẤN ĐỀ TRONG BÀI VIẾT
    # -----------------------------------------------------------------------
    # Mẫu Windows 11 kết nối điện thoại / tính năng mới
    if "windows 11" in t_lower and "kết nối" in t_lower and "điện thoại" in t_lower:
        if "chuyển tệp" in t_lower:
            return [
                "Windows 11 kết nối sâu hơn với điện thoại",
                "Cách kết nối Windows 11 với điện thoại chuyển tệp dễ dàng"
            ]
        return [
            "Windows 11 kết nối sâu hơn với điện thoại",
            "Tính năng kết nối điện thoại mới trên Windows 11"
        ]

    # Mẫu VNeID liên kết mạng xã hội / lưu trú / tài khoản
    if "vneid" in t_lower:
        if "mạng xã hội" in t_lower or "livestream" in t_lower or "chứng khoán" in t_lower:
            return [
                "Liên kết tài khoản mạng xã hội với VNeID trước 31/12",
                "Hướng dẫn xác thực mạng xã hội và tài khoản livestream trên VNeID"
            ]
        if "11 nhóm tài khoản" in t_lower or ("nhóm tài khoản" in t_lower and "xác thực" in t_lower):
            return ["11 nhóm tài khoản bắt buộc liên kết xác thực trên VNeID"]
        if "thông báo lưu trú" in t_lower:
            return ["Hướng dẫn thông báo lưu trú trên VNeID mới nhất"]
        if "góp ý" in t_lower:
            return ["Cách góp ý dự thảo luật trên ứng dụng VNeID"]

    # Mẫu Steam tặng game miễn phí
    if "steam" in t_lower:
        if "miễn phí" in t_lower or "tặng" in t_lower:
            if "4 tựa game" in t_lower or "thêm" in t_lower:
                return ["Top game miễn phí mới xuất hiện trên Steam đáng chơi nhất"]
            return ["Cách nhận game bản quyền miễn phí 100% trên Steam hôm nay"]
        if "gabe newell" in t_lower or "valve" in t_lower:
            return ["Tầm nhìn của Valve và Gabe Newell về nền tảng Steam"]

    # Mẫu LMHT / CKTG
    if "cktg" in t_lower or "lmht" in t_lower or "liên minh huyền thoại" in t_lower:
        if "lịch thi đấu" in t_lower:
            return ["Lịch thi đấu CKTG LMHT mới nhất"]
        if "trực tiếp" in t_lower or "link xem" in t_lower:
            m_match = re.search(r":\s*([A-Z0-9]+\s+tái đấu\s+[A-Z0-9]+|[A-Z0-9]+\s+vs\s+[A-Z0-9]+)", t, flags=re.I)
            if m_match:
                return [f"Trực tiếp CKTG LMHT: {m_match.group(1)}"]
            return ["Link xem trực tiếp CKTG LMHT hôm nay"]
        if "nhánh thua" in t_lower or "thất thủ" in t_lower:
            return ["Kết quả CKTG LMHT mới nhất hôm nay"]

    # Mẫu GTA 6
    if "gta 6" in t_lower or "gta vi" in t_lower:
        if "trailer" in t_lower:
            return ["Trailer chính thức GTA 6 và cốt truyện nhân vật Jason"]
        if "tranh cãi" in t_lower:
            return ["Vì sao GTA 6 gây tranh cãi trước ngày ra mắt"]
        if "ô tô bay" in t_lower or "tesla" in t_lower:
            return ["GTA 6 bị so sánh tiến độ ra mắt với ô tô bay Tesla"]
        if "cấu hình" in t_lower:
            return ["Cấu hình chơi GTA 6 trên PC và ngày ra mắt"]

    # Mẫu RTX 5090 / Card đồ họa
    if "rtx 5090" in t_lower:
        if "300 triệu" in t_lower or "đám cưới" in t_lower or "chú rể" in t_lower or "quà cưới" in t_lower:
            return [
                "Card đồ họa RTX 5090 giá hơn 300 triệu làm quà cưới gây sốt",
                "Đánh giá hiệu năng và giá bán card đồ họa NVIDIA RTX 5090"
            ]
        return ["Đánh giá hiệu năng và giá bán card đồ họa RTX 5090"]

    # Mẫu Mã độc / Bảo mật
    if "mã độc" in t_lower or "bảo mật" in t_lower:
        if "mã độc tống tiền" in t_lower or "ransomware" in t_lower:
            if "sao lưu" in t_lower or "phục hồi" in t_lower:
                return ["Cách sao lưu và phục hồi dữ liệu khi bị mã độc tống tiền"]
            return ["Cảnh báo mã độc tống tiền tấn công doanh nghiệp và cách phòng tránh"]
        if "lập trình với ai" in t_lower:
            return ["Nguyên tắc bảo mật an toàn khi lập trình với AI"]

    # Mẫu YouTube
    if "youtube" in t_lower:
        if "tính năng mới" in t_lower and "sáng tạo nội dung" in t_lower:
            return ["Tính năng mới của YouTube ảnh hưởng gì đến nhà sáng tạo nội dung"]
        if "dạy học trên youtube" in t_lower or "thầy giáo youtube" in t_lower:
            return ["Xu hướng xây dựng kênh YouTube giáo dục kiếm tiền"]

    # Mẫu TikTok
    if "tiktok" in t_lower:
        if "tiktok shop" in t_lower:
            return ["Sự kiện TikTok Shop Festive Growth kết nối Brand và Creator"]
        if "kiện tiktok" in t_lower or "tính năng an toàn" in t_lower:
            return ["TikTok bị kiện vì tính năng an toàn với người dùng trẻ em"]
        if "bác sĩ tiktok" in t_lower:
            return ["Cảnh báo trào lưu nghe theo bác sĩ tự xưng trên TikTok"]

    # -----------------------------------------------------------------------
    # 2. TRÍCH XUẤT MỆNH ĐỀ TỰ NHIÊN TỪ TIÊU ĐỀ (KHÔNG CẮT CỤT GIỮA CHỪNG)
    # -----------------------------------------------------------------------
    clauses = [c.strip() for c in re.split(r"[:\?\|\–\—]| - ", t) if len(c.strip().split()) >= 4]
    if not clauses:
        clauses = [t]

    chosen_clause = clauses[0]
    for cl in clauses:
        if core_lower in cl.lower():
            chosen_clause = cl
            break

    # Chỉ tách theo dấu phẩy nếu các phần không phải là danh sách liệt kê ngắn (VD: "Zalo, TikTok, Facebook...")
    sub_parts = [sp.strip() for sp in chosen_clause.split(",") if sp.strip()]
    if len(sub_parts) == 2 and len(sub_parts[0].split()) >= 4 and len(sub_parts[1].split()) >= 4:
        for sp in sub_parts:
            sp_words = sp.split()
            if core_lower in sp.lower() and 5 <= len(sp_words) <= 14:
                chosen_clause = sp
                break

    words = chosen_clause.split()

    while words and words[0].lower().strip(",.;:\"'") in LEADING_NOISE_WORDS:
        words.pop(0)

    # Giữ trọn vẹn mệnh đề tự nhiên (tối đa 16 từ) để không bị cắt cụt câu
    if len(words) > 16:
        words = words[:15]

    while words and words[-1].lower().strip(",.;:\"'") in TRAILING_NOISE_WORDS:
        words.pop()

    if not words:
        return []

    result = " ".join(words).strip(" ,.;:-?!\"'")
    if len(result) > 1:
        result = result[0].upper() + result[1:]
    return [result]


def _norm_tokens(s: str) -> set:
    return set(re.findall(r"\w+", s.lower()))


def _is_similar_kw(a: str, b: str) -> bool:
    sa, sb = _norm_tokens(a), _norm_tokens(b)
    if not sa or not sb:
        return False
    return len(sa & sb) / len(sa | sb) >= 0.72


def suggest_seo_keywords(keyword: str, cluster_id: str, articles: List[Dict], limit: int = 3) -> List[Dict]:
    """
    Từ Keyword thu thập + Top 3 bài viết -> Sinh ra danh sách Keyword gợi ý để viết bài SEO trên website.
    """
    core_entity = keyword
    for p, canon in KNOWN_TECH_ENTITIES:
        if canon.lower() == (cluster_id or "").lower():
            core_entity = p
            break

    suggestions: List[Dict] = []

    for art in articles:
        raw_title = art.get("title", "")
        if not raw_title:
            continue

        cleaned_title = clean_article_title(raw_title)
        seo_kws = _synthesize_problem_keyword(raw_title, core_entity)

        for seo_kw in seo_kws:
            if not seo_kw or len(seo_kw.split()) < 3:
                continue

            duplicate = False
            for existing in suggestions:
                if _is_similar_kw(existing["keyword"], seo_kw):
                    existing["support"] += 1
                    duplicate = True
                    break

            if not duplicate:
                suggestions.append({
                    "keyword": seo_kw,
                    "intent": _detect_intent_label(cleaned_title),
                    "support": 1,
                    "based_on": f"[{art.get('source_name', 'Báo công nghệ')}] {cleaned_title}"
                })

    suggestions.sort(key=lambda x: (-x["support"]))

    return [
        {
            "keyword": item["keyword"],
            "intent": item["intent"],
            "based_on": item["based_on"]
        }
        for item in suggestions[:limit]
    ]
