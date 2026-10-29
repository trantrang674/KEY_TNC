# -*- coding: utf-8 -*-
"""Tạo bản trang tĩnh đăng nhập được để đăng lên GitHub Pages (thư mục site/).

Luồng: chạy engine -> báo cáo -> ĐẨY báo cáo lên Supabase (bảng daily_reports, chỉ tài khoản đã duyệt đọc được)
       -> xuất site/index.html (đã điền cấu hình Supabase công khai) + logo. KHÔNG xuất report.json công khai.

Biến môi trường cần có:
  SUPABASE_URL, SUPABASE_ANON_KEY   (công khai, nhúng vào trang)
  SUPABASE_SERVICE_KEY              (bí mật, chỉ dùng ở đây để ghi báo cáo, KHÔNG nhúng vào trang)
  SERPAPI_API_KEY                   (khi chạy engine)
Chạy cục bộ:  python build_static.py             (dùng .env)
Cờ --reuse:   dùng data/latest_top10_report.json có sẵn, không chạy engine (không tốn lượt SerpApi).
Cờ --ui-only: chỉ xuất lại giao diện, giữ nguyên các báo cáo đã có trên Supabase (không chạy engine, không ghi báo cáo).
Xem thử cục bộ: python -m http.server -d site 8080
"""
import json
import os
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent
SITE = ROOT / "site"
MARKERS = {
    "STATIC_MODE": ("const STATIC_MODE = false; /*STATIC_MODE_MARKER*/", "const STATIC_MODE = true;"),
    "URL": ('const SUPABASE_URL = ""; /*SUPABASE_URL_MARKER*/', "const SUPABASE_URL = {value};"),
    "KEY": ('const SUPABASE_ANON_KEY = ""; /*SUPABASE_ANON_KEY_MARKER*/', "const SUPABASE_ANON_KEY = {value};"),
}


def need(name: str) -> str:
    val = os.getenv(name, "").strip()
    if not val:
        sys.exit(f"Thiếu biến môi trường {name}.")
    return val


def publish_report(report: dict, url: str, service_key: str) -> None:
    """Ghi báo cáo của ngày (giờ VN) vào Supabase bằng service_role (bỏ qua RLS)."""
    gen = report.get("generated_at", "")           # 'dd/mm/YYYY HH:MM:SS'
    try:
        d, m, y = gen[:10].split("/")
        report_date = f"{y}-{m}-{d}"
    except Exception:
        sys.exit(f"generated_at không đúng định dạng: {gen!r}")
    r = requests.post(
        f"{url}/rest/v1/daily_reports?on_conflict=report_date",
        headers={"apikey": service_key, "Authorization": f"Bearer {service_key}",
                 "Content-Type": "application/json", "Prefer": "resolution=merge-duplicates,return=minimal"},
        data=json.dumps([{"report_date": report_date, "report": report,
                          "updated_at": datetime.now(timezone.utc).isoformat()}],
                        ensure_ascii=False).encode("utf-8"),
        timeout=60,
    )
    if r.status_code >= 300:
        sys.exit(f"Không ghi được báo cáo lên Supabase ({r.status_code}): {r.text[:300]}\n"
                 "Đã chạy database/auth_postgres.sql chưa? Khóa SUPABASE_SERVICE_KEY có đúng không?")
    print(f"Đã đẩy báo cáo ngày {report_date} lên Supabase.")


def notify_zalo(report: dict) -> None:
    """Báo Top keyword qua Zalo Bot sau mỗi lần quét. Bỏ qua êm nếu chưa cấu hình; lỗi không làm hỏng bản dựng."""
    token = os.getenv("ZALO_BOT_TOKEN", "").strip()
    chat_id = os.getenv("ZALO_CHAT_ID", "").strip()
    if not token or not chat_id:
        return
    owner, _, repo = os.getenv("GITHUB_REPOSITORY", "").partition("/")
    link = os.getenv("ZALO_REPORT_URL", "").strip() or (f"https://{owner}.github.io/{repo}/" if repo else "")
    kws = report.get("top_10_keywords", [])
    top3 = "\n".join(f"  {i}. {k.get('keyword', '')}" for i, k in enumerate(kws[:3], start=1))
    text = (f"💥 Helu, em vừa quét Keyword_Ngành vào Website của chị - Xong lúc {report.get('generated_at', '')}\n"
            f"📊 Có {len(kws)} keyword mới, Top 3:\n{top3}\n"
            f"👉 Chị vào xem báo cáo trong link này: {link}")
    try:
        requests.post(f"https://bot-api.zaloplatforms.com/bot{token}/sendMessage",
                      json={"chat_id": chat_id, "text": text}, timeout=30)
        print("Đã báo kết quả qua Zalo.")
    except Exception as e:
        print(f"CẢNH BÁO: không gửi được tin Zalo ({type(e).__name__}).")


def main() -> None:
    load_dotenv(ROOT / ".env")
    url = need("SUPABASE_URL").rstrip("/")
    anon_key = need("SUPABASE_ANON_KEY")
    ui_only = "--ui-only" in sys.argv
    service_key = os.getenv("SUPABASE_SERVICE_KEY", "").strip() if ui_only else need("SUPABASE_SERVICE_KEY")
    if anon_key == service_key:
        sys.exit("SUPABASE_ANON_KEY đang trùng SUPABASE_SERVICE_KEY. Khóa bí mật tuyệt đối không được nhúng vào trang web.")

    if ui_only:
        report = None
    elif "--reuse" in sys.argv:
        report = json.loads((ROOT / "data" / "latest_top10_report.json").read_text(encoding="utf-8"))
    else:
        from backend.engine import build_daily_top10_report
        report = build_daily_top10_report(max_hours=48)

        apis = report.get("serpapi_status", {}).get("apis_called", {})
        bad = {k: v.get("status") for k, v in apis.items() if v.get("status") != "success"}
        if not apis or len(bad) == len(apis):
            sys.exit(f"Cả 4 cổng SerpApi đều lỗi hoặc không chạy ({bad or 'không có kết quả'}). "
                     "Kiểm tra Secret SERPAPI_API_KEY. Không xuất bản để giữ báo cáo cũ.")
        if bad:
            print(f"CẢNH BÁO: một số cổng SerpApi lỗi: {bad}")

    if report is not None and not report.get("top_10_keywords"):
        sys.exit("Báo cáo rỗng (không có keyword nào). Không xuất bản để tránh ghi đè bằng dữ liệu trống.")

    html = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    for old, new in MARKERS.values():
        if old not in html:
            sys.exit(f"Không thấy marker trong frontend/index.html: {old}")
    html = html.replace(MARKERS["STATIC_MODE"][0], MARKERS["STATIC_MODE"][1])
    html = html.replace(MARKERS["URL"][0], MARKERS["URL"][1].format(value=json.dumps(url)))
    html = html.replace(MARKERS["KEY"][0], MARKERS["KEY"][1].format(value=json.dumps(anon_key)))

    if report is not None:
        publish_report(report, url, service_key)
        notify_zalo(report)

    if SITE.exists():
        shutil.rmtree(SITE)
    SITE.mkdir()
    (SITE / "index.html").write_text(html, encoding="utf-8")
    shutil.copy(ROOT / "frontend" / "logo.png", SITE / "logo.png")
    (SITE / ".nojekyll").write_text("", encoding="utf-8")
    if report is None:
        print(f"Đã xuất {SITE} — chỉ giao diện, dùng các báo cáo đã có trên Supabase")
    else:
        print(f"Đã xuất {SITE} — {len(report['top_10_keywords'])} keyword, cập nhật {report.get('generated_at')}")


if __name__ == "__main__":
    main()
