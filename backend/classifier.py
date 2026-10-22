# -*- coding: utf-8 -*-
"""
Module phân loại 9 Ngách Nội Dung Chiến Lược & Trích xuất Keyword Tin Tức Công Nghệ.
"""

import re
from typing import Dict, List, Tuple

# Định nghĩa 9 Ngách Nội Dung Chiến Lược
NICHES = {
    "HARDWARE_COMPONENT": {
        "id": "HARDWARE_COMPONENT",
        "name": "Linh kiện - Phần Cứng",
        "badge_color": "emerald",
        "group": "Sát sườn ngành hàng",
        "keywords": [
            "rtx", "gtx", "geforce", "radeon", "rx ", "dlss", "fsr", "ray tracing",
            "card đồ họa", "vga", "gpu", "cpu", "vi xử lý", "chip ", "core i", "core ultra",
            "ryzen", "threadripper", "intel", "amd", "nvidia", "mainboard", "bo mạch chủ",
            "ram ", "ddr5", "ddr6", "ssd", "nvme", "ổ cứng", "màn hình", "oled", "mini-led",
            "tản nhiệt", "psu", "nguồn máy tính", "case", "build pc", "pc gaming", "laptop",
            "macbook", "asus", "rog", "msi", "gigabyte", "acer", "lenovo", "dell", "hp",
            "wi-fi 7", "wifi 7", "thunderbolt", "bàn phím cơ", "chuột gaming", "tai nghe"
        ]
    },
    "OS_SOFTWARE": {
        "id": "OS_SOFTWARE",
        "name": "HĐH - Phần mềm",
        "badge_color": "blue",
        "group": "Sát sườn ngành hàng",
        "keywords": [
            "windows 11", "windows 12", "windows 10", "bản cập nhật windows", "update windows",
            "microsoft office", "office 365", "microsoft 365", "word", "excel", "powerpoint",
            "copilot pc", "windows bản quyền", "phần mềm bản quyền", "key bản quyền",
            "ios ", "ios 18", "ios 19", "ios 26", "ios 27", "ipados", "macos", "one ui",
            "android 15", "android 16", "android 17", "hyperos", "harmonyos", "linux"
        ]
    },
    "BIG_TECH_EVENT": {
        "id": "BIG_TECH_EVENT",
        "name": "Có thể quan tâm",
        "badge_color": "indigo",
        "group": "Sát sườn ngành hàng",
        "keywords": [
            "apple", "ipad", "microsoft", "google", "samsung",
            "ces ", "computex", "wwdc", "google i/o", "ra mắt", "sự kiện",
            "công bố", "sony", "playstation", "ps5", "ps6",
            "nintendo switch", "xbox"
        ]
    },
    "GAME_TREND": {
        "id": "GAME_TREND",
        "name": "Game",
        "badge_color": "purple",
        "group": "Tin tức Hot & Trend",
        "keywords": [
            "gta 6", "gta vi", "grand theft auto", "black myth", "wukong", "steam", "epic games",
            "game ", "tựa game", "game thủ", "cấu hình", "fps", "liên minh huyền thoại", "lmht",
            "lol", "valorant", "cs2", "counter-strike", "pubg", "genshin impact", "honkai",
            "minecraft", "roblox", "ea sports", "fc online", "esports", "cktg", "t1 ", "faker",
            "riot games", "ubisoft", "rockstar", "capcom", "resident evil", "monster hunter",
            "elden ring", "cyberpunk"
        ]
    },
    "AI_UPDATES": {
        "id": "AI_UPDATES",
        "name": "A.I",
        "badge_color": "amber",
        "group": "Tin tức Hot & Trend",
        "keywords": [
            "ai ", "trí tuệ nhân tạo", "chatgpt", "gpt-4", "gpt-5", "openai", "claude", "anthropic",
            "gemini", "google ai", "meta ai", "llama", "copilot", "deepseek", "grok", "xai",
            "midjourney", "sora", "tạo ảnh ai", "tạo video ai", "chatbot", "llm", "npu", "ai pc",
            "apple intelligence", "galaxy ai", "agent"
        ]
    },
    "SOCIAL_APPS": {
        "id": "SOCIAL_APPS",
        "name": "Mạng xã hội - App",
        "badge_color": "pink",
        "group": "Tin tức Hot & Trend",
        "keywords": [
            "facebook", "messenger", "instagram", "threads", "meta ", "tiktok", "zalo",
            "youtube", "google drive", "gmail", "google maps", "google photos", "chrome",
            "capcut", "canva", "discord", "telegram", "whatsapp", "x (twitter)", "mạng xã hội",
            "ứng dụng", "tính năng mới", "sập mạng", "lỗi facebook", "lỗi youtube"
        ]
    },
    "GOV_DIGITAL_POLICY": {
        "id": "GOV_DIGITAL_POLICY",
        "name": "Chính sách - Quy định",
        "badge_color": "red",
        "group": "Tin tức Hot & Trend",
        "keywords": [
            "vneid", "định danh", "xác thực", "bộ công an", "bộ thông tin", "bộ tttt",
            "chính phủ", "nghị định", "quy định", "bắt buộc", "vật phẩm ảo", "cấp phép game",
            "thuế", "căn cước", "sim rác", "sinh trắc học", "ngân hàng", "chuyển khoản",
            "bản quyền phần mềm", "phạt", "luật", "cục phát thanh", "cục an toàn thông tin"
        ]
    },
    "CYBERSECURITY_ALERT": {
        "id": "CYBERSECURITY_ALERT",
        "name": "An ninh mạng",
        "badge_color": "rose",
        "group": "Mở rộng hữu ích",
        "keywords": [
            "mã độc", "virus", "hacker", "tấn công mạng", "ransomware", "lỗ hổng", "bảo mật",
            "lừa đảo", "deepfake", "chiếm đoạt", "đánh cắp", "cảnh báo", "an ninh mạng",
            "rò rỉ dữ liệu", "mật khẩu", "2fa", "xác thực 2 lớp", "phishing"
        ]
    },
    "PC_TIPS_FREE_GAMES": {
        "id": "PC_TIPS_FREE_GAMES",
        "name": "Tối ưu - Sửa lỗi",
        "badge_color": "teal",
        "group": "Mở rộng hữu ích",
        "keywords": [
            "miễn phí", "tặng game", "free game", "nhận game", "sửa lỗi", "khắc phục",
            "màn hình xanh", "bsod", "tụt fps", "giật lag", "tối ưu", "driver", "thủ thuật",
            "hướng dẫn", "cách tải", "cách cài", "cách bật", "cách tắt", "phím tắt"
        ]
    }
}

# Các từ khóa rác / khuyến mãi nội bộ / ngoài ngành cần loại bỏ
PROMO_NOISE_PATTERNS = [
    r"xả kho", r"giảm giá sốc", r"deal hời", r"flash sale", r"khuyến mãi cuối tuần",
    r"mua 1 tặng 1", r"trả góp 0%", r"thu cũ đổi mới", r"khai trương cửa hàng",
    r"tuyển dụng", r"lịch nghỉ lễ", r"voucher giảm",
    r"giáo dục steam", r"open steam day", r"mô hình steam", r"ngày hội steam",
    r"máy sấy", r"uốn duỗi tóc", r"nồi chiên", r"máy hút bụi", r"robot hút bụi",
    r"quà 20/10", r"mừng 20/10", r"giảm mạnh mừng", r"20/10 thứ mấy", r"lời chúc 20/10",
    r"thiệp 20/10", r"ngày phụ nữ việt nam"
]

# Danh sách các thực thể công nghệ / cụm từ khóa nổi bật để ưu tiên bắt chính xác
KNOWN_TECH_ENTITIES = [
    # Hệ điều hành & Phần mềm
    ("Windows 11 24H2", "Windows 11 24H2"),
    ("Windows 11", "Windows 11"),
    ("Windows 12", "Windows 12"),
    ("Windows 10", "Windows 10"),
    ("Microsoft 365", "Microsoft 365"),
    ("Microsoft Office", "Microsoft Office"),
    ("iOS 18.2", "iOS 18.2"),
    ("iOS 18.3", "iOS 18.3"),
    ("iOS 18.4", "iOS 18.4"),
    ("iOS 18", "iOS 18"),
    ("iOS 19", "iOS 19"),
    ("iOS 26", "iOS 26"),
    ("iOS 27", "iOS 27"),
    ("macOS Sequoia", "macOS Sequoia"),
    ("One UI 7", "One UI 7"),
    ("One UI 8", "One UI 8"),
    ("Android 15", "Android 15"),
    ("Android 16", "Android 16"),
    ("HyperOS 2", "HyperOS 2"),
    # Phần cứng & Linh kiện
    ("RTX 5090", "RTX 5090"),
    ("RTX 5080", "RTX 5080"),
    ("RTX 5070", "RTX 5070"),
    ("RTX 5060", "RTX 5060"),
    ("RTX 50", "RTX 50 Series"),
    ("RTX 40", "RTX 40 Series"),
    ("DLSS 4", "NVIDIA DLSS 4"),
    ("DLSS 3", "NVIDIA DLSS 3"),
    ("DLSS", "Công nghệ NVIDIA DLSS"),
    ("AMD FSR", "AMD FSR"),
    ("Ryzen 9000", "AMD Ryzen 9000"),
    ("Ryzen 7 9800X3D", "Ryzen 7 9800X3D"),
    ("Core Ultra", "Intel Core Ultra"),
    ("Intel thế hệ 15", "Intel Gen 15"),
    ("Wi-Fi 7", "Công nghệ Wi-Fi 7"),
    ("MacBook M4", "MacBook Pro M4"),
    ("Chip M4", "Chip Apple M4"),
    ("Chip M5", "Chip Apple M5"),
    ("Nintendo Switch 2", "Nintendo Switch 2"),
    ("PS5 Pro", "PlayStation 5 Pro"),
    # AI
    ("ChatGPT", "ChatGPT"),
    ("GPT-5", "OpenAI GPT-5"),
    ("GPT-4o", "OpenAI GPT-4o"),
    ("OpenAI o1", "OpenAI o1"),
    ("OpenAI o3", "OpenAI o3"),
    ("Claude 3.5", "Claude 3.5 Sonnet"),
    ("Claude 3.7", "Claude 3.7"),
    ("Claude 4", "Claude AI"),
    ("Claude", "Claude AI"),
    ("Google Gemini", "Google Gemini"),
    ("Gemini 2.0", "Google Gemini 2.0"),
    ("Gemini 2.5", "Google Gemini 2.5"),
    ("Gemini", "Google Gemini"),
    ("DeepSeek", "DeepSeek AI"),
    ("Meta AI", "Meta AI"),
    ("Copilot", "Microsoft Copilot"),
    ("Grok", "Grok AI"),
    ("Apple Intelligence", "Apple Intelligence"),
    ("Sora", "OpenAI Sora"),
    # Game
    ("GTA 6", "GTA 6 (GTA VI)"),
    ("GTA VI", "GTA 6 (GTA VI)"),
    ("Black Myth: Wukong", "Black Myth: Wukong"),
    ("Wukong", "Black Myth: Wukong"),
    ("Liên Minh Huyền Thoại", "Liên Minh Huyền Thoại"),
    ("LMHT", "Liên Minh Huyền Thoại"),
    ("Valorant", "Valorant"),
    ("Counter-Strike 2", "Counter-Strike 2 (CS2)"),
    ("CS2", "Counter-Strike 2 (CS2)"),
    ("Genshin Impact", "Genshin Impact"),
    ("Monster Hunter Wilds", "Monster Hunter Wilds"),
    ("Assassin's Creed Shadows", "Assassin's Creed Shadows"),
    ("Elden Ring", "Elden Ring"),
    ("Steam", "Nền tảng Steam"),
    ("Epic Games", "Epic Games tặng game"),
    ("T1", "Đội tuyển T1 / Faker"),
    ("Faker", "Đội tuyển T1 / Faker"),
    # Mạng xã hội & Ứng dụng
    ("Facebook", "Tính năng mới Facebook"),
    ("Messenger", "Ứng dụng Messenger"),
    ("Instagram", "Tính năng Instagram"),
    ("Threads", "Mạng xã hội Threads"),
    ("TikTok", "Xu hướng TikTok"),
    ("Zalo", "Ứng dụng Zalo"),
    ("YouTube", "Cập nhật YouTube"),
    ("Google Drive", "Google Drive"),
    ("Google Chrome", "Trình duyệt Chrome"),
    ("CapCut", "Ứng dụng CapCut"),
    ("Telegram", "Ứng dụng Telegram"),
    # Chính sách số & Quy định
    ("VNeID", "Định danh điện tử VNeID"),
    ("xác thực mạng xã hội", "Xác thực mạng xã hội VNeID"),
    ("vật phẩm ảo", "Quy định vật phẩm ảo trong Game"),
    ("phần mềm bản quyền", "Quy định Phần mềm Bản quyền"),
    ("sinh trắc học", "Xác thực Sinh trắc học"),
    ("Nghị định 147", "Nghị định 147 Quản lý Internet & Game"),
    ("lừa đảo", "Cảnh báo Lừa đảo Công nghệ"),
    ("mã độc", "Cảnh báo Mã độc & Bảo mật"),
]


def is_promo_noise(title: str) -> bool:
    """Kiểm tra xem tiêu đề có phải bài quảng cáo khuyến mãi nội bộ, mã SKU sản phẩm hoặc livestream thể thao không."""
    t_lower = title.lower()
    for pat in PROMO_NOISE_PATTERNS:
        if re.search(pat, t_lower):
            return True
    # Loại bỏ các trang cấu hình SKU sản phẩm (VD: PC GVN x GIGABYTE ... /128GD5/2TBSS/...)
    if title.count("/") >= 3:
        return True
    # Loại bỏ livestream bóng đá lạc vào từ khóa YouTube
    if "youtube live" in t_lower or ("vs " in t_lower and "live" in t_lower):
        return True
    return False


def classify_niche(title: str, summary: str = "") -> Dict:
    """Phân loại bài viết vào 1 trong 9 Ngách Nội Dung Chiến Lược."""
    text = f"{title} {summary}".lower()
    best_niche = None
    best_score = 0

    # Ưu tiên trọng số cao cho tiêu đề
    title_lower = title.lower()

    for niche_id, niche_info in NICHES.items():
        score = 0
        for kw in niche_info["keywords"]:
            if kw in title_lower:
                score += 3
            elif kw in text:
                score += 1
        if score > best_score:
            best_score = score
            best_niche = niche_info

    if not best_niche:
        # Mặc định về nhóm "Có thể quan tâm" nếu chưa khớp từ khóa cụ thể
        best_niche = NICHES["BIG_TECH_EVENT"]

    return {
        "id": best_niche["id"],
        "name": best_niche["name"],
        "badge_color": best_niche["badge_color"],
        "group": best_niche["group"],
        "relevance_score": best_score
    }


def extract_core_keyword(title: str, summary: str = "") -> Tuple[str, str]:
    """
    Trích xuất Keyword cốt lõi (Cluster Key & Display Keyword) từ tiêu đề bài viết.
    Trả về (cluster_id, display_keyword).
    """
    clean_title = re.sub(r"\s+", " ", title).strip()
    title_lower = clean_title.lower()

    # 1. Kiểm tra danh sách thực thể công nghệ/sự kiện ưu tiên
    for pattern, canonical_name in KNOWN_TECH_ENTITIES:
        if pattern.lower() in title_lower:
            # Tinh chỉnh keyword hiển thị dựa trên ngữ cảnh trong tiêu đề
            context_kw = refine_entity_keyword(canonical_name, clean_title)
            cluster_id = canonical_name.lower()
            return cluster_id, context_kw

    # 2. Tìm cụm từ viết hoa / Tên riêng sản phẩm công nghệ (VD: Galaxy A56, Redmi Note 14, RX 9070 XT...)
    model_match = re.search(
        r"\b([A-Z][A-Za-z0-9\+]{1,12}(?:\s+[A-Z0-9][A-Za-z0-9\.\-\+]{1,12}){1,3})\b",
        clean_title
    )
    if model_match:
        candidate = model_match.group(1).strip()
        if len(candidate) >= 4 and candidate.lower() not in {"việt nam", "hiện nay", "mới nhất", "chính thức"}:
            return candidate.lower(), candidate

    # 3. Nếu không có tên thực thể cố định, trích xuất mệnh đề chính của tiêu đề (trước dấu : , - , ? , |)
    parts = re.split(r"[:\?\|\–\—]| - ", clean_title)
    first_part = parts[0].strip()
    words = first_part.split()
    if 3 <= len(words) <= 8:
        return first_part.lower(), first_part
    elif len(words) > 8:
        short_phrase = " ".join(words[:7])
        return short_phrase.lower(), short_phrase
    elif len(parts) > 1:
        second_words = parts[1].strip().split()[:7]
        phrase = " ".join(second_words)
        return phrase.lower(), phrase

    fallback = " ".join(clean_title.split()[:6])
    return fallback.lower(), fallback


def refine_entity_keyword(canonical_name: str, title: str) -> str:
    """Làm giàu tên Keyword hiển thị để sát ý định tìm kiếm SEO nhất."""
    t_lower = title.lower()
    base = canonical_name

    # Bổ sung hậu tố hành động/sự kiện nếu rất rõ ràng
    if "vneid" in base.lower():
        if "mạng xã hội" in t_lower or "facebook" in t_lower:
            return "Xác thực mạng xã hội bằng VNeID"
        return "Cập nhật tính năng VNeID mới nhất"

    if "gta 6" in base.lower():
        if "cấu hình" in t_lower or "pc" in t_lower:
            return "Cấu hình GTA 6 & Ngày ra mắt"
        return "Tin tức GTA 6 (GTA VI) mới nhất"

    if "windows 11" in base.lower():
        if "lỗi" in t_lower:
            return f"Lỗi bản cập nhật {base}"
        if "cập nhật" in t_lower or "tính năng" in t_lower:
            return f"Cập nhật {base} mới nhất"

    return base


# ---------------------------------------------------------------------------
# BỘ LỌC: Loại bỏ chủ đề SẢN PHẨM ĐIỆN THOẠI DI ĐỘNG (smartphone)
# Công ty không kinh doanh mặt hàng này. Bài vẫn được giữ nếu tiêu đề có yếu tố
# PC / Windows / laptop (VD: "Windows 11 kết nối sâu hơn với điện thoại").
# ---------------------------------------------------------------------------
PHONE_PATTERNS = [
    r"\biphone\b", r"\bgalaxy\s*(s|a|z|m|f)\s?\d+", r"\bgalaxy\s*(ultra|fold|flip|ring)",
    r"\bz\s?(fold|flip)\s?\d*", r"\bsamsung\s+galaxy\b",
    r"điện thoại", r"smartphone", r"\bredmi\b", r"\bpoco\b", r"\bxiaomi\b", r"\boppo\b", r"\bvivo\b",
    r"\brealme\b", r"\bhonor\b", r"\boneplus\b", r"\bpixel\s*\d", r"\btecno\b", r"\binfinix\b",
    r"\bnubia\b", r"\bred\s?magic\b", r"\bmotorola\b", r"\bnothing phone\b", r"\bfind x\d", r"\breno\s?\d+",
    r"\bnote\s?\d+\s?(pro|plus|ultra)?", r"\biqoo\b", r"\bhuawei\s+(mate|pura|nova|pocket)",
    r"trên di động", r"di động (tăng|nhắm)", r"cụm camera", r"camera (lồi|selfie|tiềm vọng)",
    r"sạc nhanh \d+w", r"pin \d{4,5}\s*mah"
]
PC_CONTEXT_PATTERNS = [
    r"windows", r"laptop", r"\bpc\b", r"máy tính", r"macbook", r"\boffice\b", r"microsoft 365",
    r"card đồ họa", r"\brtx\b", r"\bgtx\b", r"\bcpu\b", r"\bgpu\b", r"ryzen", r"core i", r"core ultra",
    r"mainboard", r"màn hình", r"ssd", r"\bram\b", r"bàn phím", r"chuột", r"tai nghe",
    r"chrome", r"phần mềm", r"steam", r"gta", r"valorant", r"lmht", r"liên minh",
    r"chatgpt", r"gemini", r"claude", r"vneid"
]


def is_smartphone_topic(title: str, summary: str = "") -> bool:
    """True nếu bài viết xoay quanh sản phẩm điện thoại (và không gắn với PC/Windows/laptop)."""
    t = title.lower()
    if not any(re.search(p, t) for p in PHONE_PATTERNS):
        return False
    if any(re.search(p, t) for p in PC_CONTEXT_PATTERNS):
        return False
    return True

