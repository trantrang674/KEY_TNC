# -*- coding: utf-8 -*-
"""Tạo bản trang tĩnh để đăng lên GitHub Pages vào thư mục site/.
Chạy engine -> report.json, rồi sao chép frontend (bật STATIC_MODE).
Chạy cục bộ:  python build_static.py   (xem thử: python -m http.server -d site 8080)
Cờ --reuse: không chạy engine, dùng data/latest_top10_report.json có sẵn (không tốn lượt SerpApi).
"""
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SITE = ROOT / "site"
MARKER = "const STATIC_MODE = false; /*STATIC_MODE_MARKER*/"


def main() -> None:
    if "--reuse" in sys.argv:
        report = json.loads((ROOT / "data" / "latest_top10_report.json").read_text(encoding="utf-8"))
    else:
        from backend.engine import build_daily_top10_report
        report = build_daily_top10_report(max_hours=48)

    if "--reuse" not in sys.argv:
        apis = report.get("serpapi_status", {}).get("apis_called", {})
        bad = {k: v.get("status") for k, v in apis.items() if v.get("status") != "success"}
        if not apis or len(bad) == len(apis):
            sys.exit(f"Cả 4 cổng SerpApi đều lỗi hoặc không chạy ({bad or 'không có kết quả'}). "
                     "Kiểm tra Secret SERPAPI_API_KEY. Không xuất bản để giữ trang cũ.")
        if bad:
            print(f"CẢNH BÁO: một số cổng SerpApi lỗi: {bad}")

    if not report.get("top_10_keywords"):
        sys.exit("Báo cáo rỗng (không có keyword nào). Không xuất bản để tránh ghi đè trang cũ bằng trang trống.")

    html = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    if MARKER not in html:
        sys.exit("Không thấy STATIC_MODE_MARKER trong frontend/index.html")

    if SITE.exists():
        shutil.rmtree(SITE)
    SITE.mkdir()
    (SITE / "index.html").write_text(html.replace(MARKER, "const STATIC_MODE = true;"), encoding="utf-8")
    shutil.copy(ROOT / "frontend" / "logo.png", SITE / "logo.png")
    (SITE / "report.json").write_text(json.dumps(report, ensure_ascii=False), encoding="utf-8")
    (SITE / ".nojekyll").write_text("", encoding="utf-8")
    print(f"Đã xuất {SITE} — {len(report['top_10_keywords'])} keyword, cập nhật {report.get('generated_at')}")


if __name__ == "__main__":
    main()
