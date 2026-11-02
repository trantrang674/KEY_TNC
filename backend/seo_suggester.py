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
MAX_SUGGEST_WORDS = 8
MIN_SUGGEST_WORDS = 2
MAX_PERSON_PHRASE_WORDS = 12  # keyword dài đủ ý cho tên người gắn với 1 sự kiện

# Từ lửng: không được đứng cuối keyword (cụm bị cắt cụt thì vô nghĩa)
DANGLING_TOKENS = (NOISE_TOKENS - {"mới", "nhất"}) | {
    "từ", "sang", "ở", "về", "trên", "vào", "khi", "một", "các", "những", "nên", "dung", "kinh",
    "này", "đó", "nhiều", "rất", "cũng", "đều", "chỉ", "không", "vẫn", "lại", "tới", "đến", "theo", "tự", "thành",
}
# Thực thể chứa các từ này là câu/lời khuyên dài, không phải tên riêng -> không dùng làm lõi keyword
BAD_ENTITY_TOKENS = {"nên", "nào", "và", "là", "làm", "sao", "thế", "không"}
# Tiền tố ý định bị gỡ khỏi thực thể (VD 'Cách tải Steam' -> 'Steam')
ENTITY_LEADING_INTENT = {"cách", "tải", "chơi", "mua", "xu", "hướng", "cập", "nhật", "ứng", "dụng", "tính", "năng", "mới"}
# Động từ đứng cuối mà vẫn trọn nghĩa
SELF_SUFFICIENT_VERBS = {"ra mắt", "lộ", "rò rỉ", "mở bán", "lên kệ", "đóng cửa", "kết thúc", "bắt đầu"}


def _strip_dangling(words: List[str]) -> List[str]:
    words = list(words)
    while words and words[-1].lower().strip(",.;:!?\"'") in DANGLING_TOKENS:
        words.pop()
    return words


def _has_repeated_word(phrase: str) -> bool:
    toks = [t for t in re.findall(r"\w+", phrase.lower()) if len(t) >= 2]
    return len(toks) != len(set(toks))

# (regex trên tiêu đề, mẫu keyword, nhãn ý định). Thứ tự = độ ưu tiên khi số bài ủng hộ bằng nhau.
INTENT_RULES = [
    (r"trailer|teaser", "{E} trailer", "Keyword Tính năng / Tin mới"),
    (r"ngày ra mắt|ra mắt|phát hành|lên kệ|mở bán", "{E} ngày ra mắt", "Keyword Tính năng / Tin mới"),
    (r"cấu hình|yêu cầu hệ thống|thông số", "cấu hình {E}", "Keyword Cấu hình / Đánh giá"),
    (r"(?<!đánh )\bgiá\b|bao nhiêu tiền|giá bán", "giá {E}", "Keyword Giá bán / Mua hàng"),
    (r"lỗi|khắc phục|sửa chữa|treo máy|crash|không mở được", "cách sửa lỗi {E}", "Keyword Khắc phục lỗi"),
    (r"lịch thi đấu|lịch đấu", "lịch thi đấu {E}", "Keyword Lịch / Kết quả"),
    (r"link xem|xem trực tiếp|trực tiếp trận", "link xem trực tiếp {E}", "Keyword Lịch / Kết quả"),
    (r"tải về|tải xuống|download|cài đặt", "cách tải {E}", "Keyword Hướng dẫn / Thủ thuật"),
    (r"so sánh|đọ sức|đối đầu", "so sánh {E}", "Keyword Cấu hình / Đánh giá"),
    (r"quy định|nghị định|thông tư|bắt buộc|xác thực|liên kết|hạn chót", "{E} quy định mới", "Keyword Chính sách / Hướng dẫn thực hiện"),
]

# Theo bảng keyword mẫu: KHÔNG độn cụm mặc định (VD "{E} mới nhất", "đánh giá {E}", "hướng dẫn {E}").
DEFAULT_TEMPLATES: list = []

# Hậu tố / tiền tố chung chung -> keyword chỉ gồm <thực thể> + cụm này bị loại (không đủ viết thành 1 bài SEO)
GENERIC_PHRASES = [
    "mới nhất", "tính năng mới", "có gì mới", "đánh giá", "review", "hướng dẫn", "cách dùng",
    "cảnh báo", "cảnh báo lừa đảo", "lừa đảo", "ngày ra mắt", "tin tức", "tin mới", "cập nhật",
    "cập nhật mới", "tin hot", "là gì", "quy định mới",
]
# Thực thể quá chung (app/mạng xã hội/chủ đề) -> chỉ được dùng khi có sự kiện cụ thể từ tiêu đề bài
_GENERIC_WORDS = {
    "mới", "nhất", "tính", "năng", "review", "cảnh", "báo", "lừa", "đảo", "tin", "tức", "hot",
    "cập", "nhật", "xu", "hướng", "quy", "định",
}
GENERIC_ENTITIES = {
    "tiktok", "youtube", "zalo", "facebook", "instagram", "lừa đảo", "cảnh báo lừa đảo",
    "cảnh báo", "ai", "công nghệ", "tin tức",
}
# Động từ / sự việc cụ thể -> giúp keyword trở thành 1 sự kiện viết được bài
EVENT_VERBS = (
    "ra mắt|giảm|giới hạn|mất|liên kết|tăng|cắt|đóng|ngừng|chạy|đoán|thêm|cấm|bán|đổi|rò rỉ|lộ|"
    "tặng|hỗ trợ|bị|thu phí|khóa|chặn|mở|dừng|hợp tác|mua lại|sa thải|vượt|đạt|"
    "từ chối|gia hạn|tiết lộ|công bố|phát hiện|tung|đưa|cho phép|phát hành|nhận|chê|bổ sung|"
    "trang bị|tích hợp|thử nghiệm|xác nhận|dùng|vá|sửa|khắc phục|nâng cấp|hạ giá|tăng giá|"
    "đóng cửa|kết thúc|bắt đầu|mở bán|lên kệ|vào"
)


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
    while len(kept) > 1 and kept[0].lower() in ENTITY_LEADING_INTENT:
        kept = kept[1:]
    entity = " ".join(kept[:MAX_ENTITY_WORDS]).strip(" ,.;:-?!\"'")
    if any(w.lower() in BAD_ENTITY_TOKENS for w in entity.split()) or len(entity.split()) < 1:
        return ""
    return entity


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
        if bare.isupper() and len(bare) <= 2 and not any(c.isdigit() for c in bare):
            break
        if not (bare[0].isupper() or any(c.isdigit() for c in bare)):
            break
        taken.append(bare)
        if tok != tok.rstrip(",.;:!?\"'"):  # token kết thúc bằng dấu câu -> dừng
            break
    if not taken:
        return None
    return f"{entity} {' '.join(taken)}"


def is_generic_keyword(phrase: str, entity: str) -> bool:
    """True nếu keyword chỉ là <thực thể> + hậu tố chung chung (VD 'VNeID mới nhất', 'Đánh giá TikTok')."""
    rest = re.sub(re.escape(entity), " ", phrase, flags=re.IGNORECASE).lower()
    rest = re.sub(r"\s+", " ", rest).strip(" ,.;:-?!\"'")
    if not rest:
        return True
    return rest in GENERIC_PHRASES or all(t in _GENERIC_WORDS for t in rest.split())


def _ends_with_bare_verb(words: List[str]) -> bool:
    """Cụm kết thúc bằng động từ trơ (VD 'Windows 11 26H2 chạy') -> chưa trọn nghĩa."""
    for n in (2, 1):
        tail = " ".join(words[-n:]).lower()
        if len(words) > n and re.fullmatch(EVENT_VERBS, tail):
            return tail not in SELF_SUFFICIENT_VERBS
    return False


def _mine_event_phrase(title: str, entity: str) -> Optional[str]:
    """Cụm sự kiện cụ thể: <thực thể> [tên gói/phiên bản] + động từ + tối đa 3 từ/số liệu
    (VD 'Google giảm dung lượng', 'Windows 11 26H2 chạy thành công', 'Claude Max 20x đổi tên thành Ultra').
    Trả None nếu cụm chưa trọn nghĩa."""
    m = re.search(
        rf"{re.escape(entity)}((?:(?:\s+(?:[A-Z][\w.+-]*|[\w.]*\d[\w.]*)){{1,2}})?)\s+((?:{EVENT_VERBS})(?:\s+[^\s,.;:!?()\[\]\"'|–—-]+){{0,3}})",
        title,
    )
    if not m:
        return None
    words = _strip_dangling(f"{entity}{m.group(1)} {m.group(2)}".split()[:MAX_SUGGEST_WORDS])
    if len(words) < MIN_SUGGEST_WORDS or _ends_with_bare_verb(words):
        return None
    phrase = " ".join(words)
    return phrase.replace("miễn", "miễn phí") if words[-1:] == ["miễn"] else phrase


def _fallback_headline_phrase(titles: List[str], entity: str) -> Optional[str]:
    """Dự phòng: lấy đoạn đầu tiêu đề bắt đầu từ thực thể, chỉ nhận khi cụm trọn nghĩa
    (không cụt, không kết thúc bằng động từ trơ, dài hơn thực thể)."""
    for title in titles:
        m = re.search(re.escape(entity), title, flags=re.IGNORECASE)
        if not m or m.start() > 12:  # thực thể phải ở đầu tiêu đề
            continue
        clause = re.split(r"[,;:!?|–—]|\s-\s", title[m.start():], maxsplit=1)[0]
        clause = re.sub(r"[\"'“”‘’()\[\]]", "", clause)
        words = _strip_dangling(clause.split()[:6])
        if len(words) > len(entity.split()) and len(words) >= MIN_SUGGEST_WORDS and not _ends_with_bare_verb(words):
            return " ".join(words)
    return None


def _is_person_like(entity: str) -> bool:
    """Tên người: 2-3 từ, mỗi từ viết hoa chữ cái đầu, không phải thực thể công nghệ đã biết."""
    words = entity.split()
    if not 2 <= len(words) <= 3 or entity.lower() in GENERIC_ENTITIES:
        return False
    if any(canon.lower() == entity.lower() or pat.lower() == entity.lower() for pat, canon in KNOWN_TECH_ENTITIES):
        return False
    return all(w[:1].isupper() and not any(c.isdigit() for c in w) and not w.isupper() for w in words)


def _person_event_phrase(titles: List[str], entity: str) -> Optional[str]:
    """Tên người luôn gắn với 1 sự kiện -> keyword DÀI đủ ý: lấy cả tiêu đề bắt đầu từ tên người
    (VD 'Sam Altman: Thật tệ khi RAM nằm trong máy người dùng')."""
    for title in titles:
        m = re.search(re.escape(entity), title, flags=re.IGNORECASE)
        if not m or m.start() > 12:
            continue
        text = re.sub(r"[\"“”‘’']", "", title[m.start():])
        text = re.sub(r"\s+", " ", text).strip()
        words = text.split()[:MAX_PERSON_PHRASE_WORDS]
        words = _strip_dangling(words)
        # giữ nguyên dấu ':' sau tên người cho dễ đọc
        phrase = " ".join(words)
        if len(words) >= len(entity.split()) + 3:
            return phrase.rstrip(" ,.;:-?!")
    return None


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

    def add(phrase: str, intent: str, based_on: str, support: float, priority: int,
            max_words: int = MAX_SUGGEST_WORDS) -> None:
        phrase = _finalize(" ".join(_strip_dangling(phrase.split())))
        long_mode = max_words > MAX_SUGGEST_WORDS
        if _has_repeated_word(phrase) and not long_mode:
            return
        if not phrase or not (MIN_SUGGEST_WORDS <= len(phrase.split()) <= max_words) or phrase.lower() == entity_low:
            return
        if is_generic_keyword(phrase, entity):
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
        if entity_low in s.lower() and s.lower() != entity_low and not is_generic_keyword(s, entity):
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
        event = _mine_event_phrase(title, entity)
        if event:
            add(event, "Sự kiện cụ thể", based_on, support=1.5, priority=-2)
        if entity_low in GENERIC_ENTITIES:
            continue  # thực thể quá chung: chỉ nhận cụm sự kiện cụ thể, không ghép mẫu
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

    # 3b. Tên người gắn với sự kiện: ưu tiên 1 keyword dài đủ ý lấy từ tiêu đề
    if _is_person_like(entity):
        clean_titles_p = [
            clean_article_title(a.get("title", "")) for a in articles
            if a.get("title") and not is_product_sku_or_live_noise(a.get("title", ""))
        ]
        long_kw = _person_event_phrase(clean_titles_p, entity)
        if long_kw:
            add(long_kw, "Sự kiện gắn với nhân vật", "Tiêu đề bài viết top", support=3.0, priority=-3,
                max_words=MAX_PERSON_PHRASE_WORDS)

    # 4. Dự phòng: chưa có keyword nào -> lấy cụm nổi bật từ tiêu đề bài mới nhất (bỏ qua thực thể quá chung)
    if not candidates and entity_low not in GENERIC_ENTITIES:
        clean_titles = [
            clean_article_title(a.get("title", "")) for a in articles
            if a.get("title") and not is_product_sku_or_live_noise(a.get("title", ""))
        ]
        fb = _fallback_headline_phrase(clean_titles, entity)
        if fb:
            add(fb, "Sự kiện nổi bật", "Tiêu đề bài viết top", support=0.3, priority=90)

    ranked = sorted(candidates.values(), key=lambda x: (-x["support"], x["priority"]))
    return [
        {"keyword": c["keyword"], "intent": c["intent"], "based_on": c["based_on"]}
        for c in ranked[:limit]
    ]
