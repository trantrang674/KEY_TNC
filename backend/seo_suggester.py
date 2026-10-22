# -*- coding: utf-8 -*-
"""
Gợi ý KEYWORD VIẾT BÀI SEO cho website, bám đúng "góc vấn đề" mà các bài viết top đang đề cập.

Luồng chuẩn:
Keyword thu thập -> Top bài viết -> Gợi ý Keyword sẽ dùng để viết bài SEO cho website.

Keyword gợi ý là CỤM NGẮN, CHÍNH XÁC (2-6 từ) theo dạng: <thực thể> + <ý định tìm kiếm>, KHÔNG sao chép tiêu đề bài.
Ví dụ:
- Keyword thu thập: "GTA 6"
  + Bài viết: "GTA 6 lộ cấu hình PC chính thức, yêu cầu RTX 4070 trở lên"
  -> Gợi ý Keyword SEO: "Cấu hình GTA 6", "GTA 6 ngày ra mắt", "GTA 6 trailer"
Nguồn gợi ý theo thứ tự ưu tiên:
1. Google Autocomplete (cụm người dùng thật sự gõ) có chứa thực thể.
2. Ý định tìm kiếm rút ra từ tiêu đề các bài viết top (cấu hình, giá, hướng dẫn, sửa lỗi, ...).
3. Các cụm mặc định phổ biến nếu chưa đủ số lượng.
"""

import html
import re
from typing import Dict, List, Optional

from backend.classifier import KNOWN_TECH_ENTITIES

# Từ chung chung bị gỡ khỏi tên thực thể khi cụm keyword không nằm trong danh sách thực thể có sẵn
GENERIC_TOKENS = {
    "tin", "tức", "mới", "nhất", "cập", "nhật", "tính", "năng", "nền", "tảng",
    "xu", "hướng", "ứng", "dụng", "công", "nghệ", "định", "danh", "điện", "tử", "cảnh", "báo",
}

# Từ thường (kể cả khi bị viết hoa toàn bộ trong tiêu đề) không được nối vào sau tên thực thể
NOISE_TOKENS = {
    "có", "gì", "là", "và", "của", "với", "cho", "để", "thì", "mà", "nào", "mới", "nhất", "hơn",
    "vs", "tại", "trong", "khi", "bị", "được", "sẽ", "đã", "đang", "ra", "thế", "sao", "như",
}

MAX_ENTITY_WORDS = 4
MAX_SUGGEST_WORDS = 6
MIN_SUGGEST_WORDS = 2

# (regex trên tiêu đề, mẫu keyword, nhãn ý định). Thứ tự = độ ưu tiên khi số bài ủng hộ bằng nhau.
INTENT_RULES = [
    (r"trailer|teaser", "{E} trailer", "Keyword Tính năng / Tin mới"),
    (r"ngày ra mắt|ra mắt|phát hành|lên kệ|mở bán", "{E} ngày ra mắt", "Keyword Tính năng / Tin mới"),
    (r"cấu hình|yêu cầu hệ thống|thông số", "cấu hình {E}", "Keyword Cấu hình / Đánh giá"),
    (r"(?<!đánh )\bgiá\b|bao nhiêu tiền|giá bán", "giá {E}", "Keyword Giá bán / Mua hàng"),
    (r"lỗi|khắc phục|sửa chữa|treo máy|crash|không mở được", "cách sửa lỗi {E}", "Keyword Khắc phục lỗi"),
    (r"lịch thi đấu|lịch đấu", "lịch thi đấu {E}", "Keyword Lịch / Kết quả"),
    (r"link xem|xem trực tiếp|trực tiếp trận", "link xem trực tiếp {E}", "Keyword Lịch / Kết quả"),
    (r"hướng dẫn|cách |mẹo|thủ thuật", "hướng dẫn {E}", "Keyword Hướng dẫn / Thủ thuật"),
    (r"tải về|tải xuống|download|cài đặt", "cách tải {E}", "Keyword Hướng dẫn / Thủ thuật"),
    (r"miễn phí|tặng game|nhận ngay|free|giveaway", "{E} miễn phí", "Keyword Săn ưu đãi / Game miễn phí"),
    (r"đánh giá|hiệu năng|benchmark|review|trải nghiệm", "đánh giá {E}", "Keyword Cấu hình / Đánh giá"),
    (r"so sánh|đọ sức|đối đầu", "so sánh {E}", "Keyword Cấu hình / Đánh giá"),
    (r"quy định|nghị định|thông tư|bắt buộc|xác thực|liên kết|hạn chót", "{E} quy định mới", "Keyword Chính sách / Hướng dẫn thực hiện"),
    (r"lừa đảo|mã độc|tống tiền|lỗ hổng|bảo mật|tấn công", "cảnh báo {E}", "Keyword Cảnh báo & Phòng tránh"),
    (r"cập nhật|tính năng mới|bản mới|nâng cấp|bổ sung", "{E} có gì mới", "Keyword Tính năng / Tin mới"),
]

DEFAULT_TEMPLATES = [
    ("{E} mới nhất", "Keyword Tin tức SEO trọng tâm"),
    ("đánh giá {E}", "Keyword Cấu hình / Đánh giá"),
    ("hướng dẫn {E}", "Keyword Hướng dẫn / Thủ thuật"),
    ("{E} có gì mới", "Keyword Tính năng / Tin mới"),
]


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
    if raw_title.strip().endswith("...") or raw_title.strip().endswith("…"):
        return True
    letters = [c for c in raw_title if c.isalpha()]
    if letters and (sum(c.isupper() for c in letters) / len(letters) > 0.7):
        return True
    return False


def _entity_from_keyword(keyword: str, cluster_id: str, titles: List[str]) -> str:
    """Rút ra tên thực thể NGẮN (vd: 'GTA 6', 'VNeID') dùng làm lõi cho mọi keyword gợi ý."""
    cid = (cluster_id or "").lower()
    titles_low = " ".join(titles).lower()
    in_titles: List[str] = []
    others: List[str] = []
    for pattern, canon in KNOWN_TECH_ENTITIES:
        if canon.lower() == cid:
            (in_titles if pattern.lower() in titles_low else others).append(pattern)
    # Ưu tiên tên viết tắt ngắn nhất đang xuất hiện trong tiêu đề (vd: 'LMHT' thay vì 'Liên Minh Huyền Thoại')
    for group in (in_titles, others):
        if group:
            return min(group, key=len)

    # Cụm không nằm trong danh sách thực thể: gỡ phần chú thích trong ngoặc và các từ chung chung
    text = re.sub(r"\([^)]*\)", " ", keyword or "")
    words = [w for w in re.split(r"\s+", text) if w]
    kept = [w for w in words if w.lower().strip(",.;:!?\"'") not in GENERIC_TOKENS]
    kept = kept or words
    return " ".join(kept[:MAX_ENTITY_WORDS]).strip(" ,.;:-?!\"'")


def _mine_following_phrase(title: str, entity: str) -> Optional[str]:
    """
    Lấy cụm ngắn ngay sau thực thể trong tiêu đề khi phần theo sau là tên riêng / phiên bản / năm
    (vd: 'VALORANT Champions 2026', 'Windows 11 26H2'). Dừng ở dấu câu hoặc từ thường.
    """
    m = re.search(re.escape(entity), title, flags=re.IGNORECASE)
    if not m:
        return None
    tail = title[m.end():]
    if not tail.startswith(" "):
        return None
    taken = []
    for tok in tail.split()[:3]:
        bare = tok.strip(",.;:!?\"'()[]")
        if bare != tok.rstrip(",.;:!?\"'") and not taken:
            break
        if not bare or bare.lower() in NOISE_TOKENS:
            break
        if not (bare[0].isupper() or any(c.isdigit() for c in bare)):
            break
        taken.append(bare)
        if tok != tok.rstrip(",.;:!?\"'"):  # token kết thúc bằng dấu câu -> dừng
            break
    if not taken:
        return None
    return f"{entity} {' '.join(taken)}"


def _detect_intent_label(text: str) -> str:
    low = text.lower()
    for pattern, _template, intent in INTENT_RULES:
        if re.search(pattern, f" {low} "):
            return intent
    return "Keyword Tin tức SEO trọng tâm"


def _finalize(phrase: str) -> str:
    phrase = re.sub(r"\s+", " ", phrase).strip(" ,.;:-?!\"'")
    return phrase[0].upper() + phrase[1:] if phrase else phrase


def _is_valid_length(phrase: str) -> bool:
    return MIN_SUGGEST_WORDS <= len(phrase.split()) <= MAX_SUGGEST_WORDS


def _norm_tokens(s: str) -> set:
    return set(re.findall(r"\w+", s.lower()))


def _is_similar_kw(a: str, b: str) -> bool:
    sa, sb = _norm_tokens(a), _norm_tokens(b)
    if not sa or not sb:
        return False
    return len(sa & sb) / len(sa | sb) >= 0.72


def suggest_seo_keywords(
    keyword: str,
    cluster_id: str,
    articles: List[Dict],
    limit: int = 3,
    autocomplete: Optional[List[str]] = None,
) -> List[Dict]:
    """
    Từ Keyword thu thập + các bài viết top -> tối đa `limit` keyword gợi ý ngắn gọn để viết bài SEO.
    """
    titles = [clean_article_title(a.get("title", "")) for a in articles if a.get("title")]
    entity = _entity_from_keyword(keyword, cluster_id, titles)
    if not entity:
        return []
    entity_low = entity.lower()

    # candidates: keyword_lower -> dict(keyword, intent, support, priority, based_on)
    candidates: Dict[str, Dict] = {}

    def add(phrase: str, intent: str, based_on: str, support: float, priority: int) -> None:
        phrase = _finalize(phrase)
        if not phrase or not _is_valid_length(phrase) or phrase.lower() == entity_low:
            return
        for existing in candidates.values():
            if _is_similar_kw(existing["keyword"], phrase):
                existing["support"] += support
                return
        candidates[phrase.lower()] = {
            "keyword": phrase, "intent": intent, "support": support,
            "priority": priority, "based_on": based_on,
        }

    # 1. Google Autocomplete: cụm người dùng thật sự tìm kiếm có chứa thực thể
    taken_auto = 0
    for sug in autocomplete or []:
        if taken_auto >= 2:  # chừa chỗ cho các gợi ý rút từ bài viết
            break
        s = re.sub(r"\s+", " ", str(sug)).strip()
        if entity_low in s.lower() and s.lower() != entity_low:
            s = re.sub(re.escape(entity), entity, s, flags=re.IGNORECASE)  # đồng nhất cách viết tên thực thể
            before = len(candidates)
            add(s, "Gợi ý tìm kiếm Google", "Google Autocomplete", support=2.0, priority=-1)
            taken_auto += len(candidates) - before

    # 2. Ý định tìm kiếm rút ra từ tiêu đề các bài viết top
    for art in articles:
        raw_title = art.get("title", "")
        if not raw_title or is_product_sku_or_live_noise(raw_title):
            continue
        title = clean_article_title(raw_title)
        title_low = f" {title.lower()} "
        based_on = f"[{art.get('source_name', 'Báo công nghệ')}] {title}"
        for prio, (pattern, template, intent) in enumerate(INTENT_RULES):
            if re.search(pattern, title_low):
                add(template.replace("{E}", entity), intent, based_on, support=1.0, priority=prio)
        mined = _mine_following_phrase(title, entity)
        if mined:
            add(mined, _detect_intent_label(title), based_on, support=0.5, priority=50)

    # 3. Bổ sung cụm mặc định nếu chưa đủ số lượng
    if len(candidates) < limit:
        for i, (template, intent) in enumerate(DEFAULT_TEMPLATES):
            add(template.replace("{E}", entity), intent, "Cụm tìm kiếm phổ biến", support=0.1, priority=100 + i)

    ranked = sorted(candidates.values(), key=lambda x: (-x["support"], x["priority"]))
    return [
        {"keyword": c["keyword"], "intent": c["intent"], "based_on": c["based_on"]}
        for c in ranked[:limit]
    ]
