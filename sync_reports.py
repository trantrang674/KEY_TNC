# -*- coding: utf-8 -*-
"""Đồng bộ report.md của từng keyword lên Supabase để nút "XEM REPORT" trên dashboard hiển thị được.

Nguồn:  <SEO_OUTPUT>/<slug>/report.md   (mặc định: tnc-seo-content/seo_output)
Đích:   seo_outlines.research.report_md (giữ nguyên các trường khác của cột research)

Khớp keyword <-> thư mục theo slug (bỏ dấu, chữ thường, nối bằng "-"), ví dụ "Claude Duet" -> claude-duet.
Mặc định chỉ XEM TRƯỚC (không ghi). Thêm --apply để ghi thật.

Biến môi trường (.env): SUPABASE_URL, SUPABASE_SERVICE_KEY. Tùy chọn: SEO_OUTPUT_DIR.
Chạy:  python sync_reports.py            (xem trước)
       python sync_reports.py --apply    (ghi lên Supabase)
"""
import os
import re
import sys
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent
DEFAULT_DIR = ROOT.parent.parent / "tnc-seo-content" / "seo_output"


def slugify(text: str) -> str:
    t = unicodedata.normalize("NFD", text.replace("đ", "d").replace("Đ", "D"))
    t = "".join(c for c in t if unicodedata.category(c) != "Mn").lower()
    return re.sub(r"[^a-z0-9]+", "-", t).strip("-")


def need(name: str) -> str:
    val = os.getenv(name, "").strip()
    if not val:
        sys.exit(f"Thiếu biến môi trường {name}.")
    return val


def main() -> None:
    load_dotenv(ROOT / ".env")
    url = need("SUPABASE_URL").rstrip("/")
    key = need("SUPABASE_SERVICE_KEY")
    apply = "--apply" in sys.argv
    out_dir = Path(os.getenv("SEO_OUTPUT_DIR", "").strip() or DEFAULT_DIR)
    if not out_dir.is_dir():
        sys.exit(f"Không thấy thư mục seo_output: {out_dir} (đặt SEO_OUTPUT_DIR trong .env)")

    reports = {}
    for d in out_dir.iterdir():
        f = d / "report.md"
        if d.is_dir() and f.is_file():
            reports[slugify(d.name)] = f

    headers = {"apikey": key, "Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    r = requests.get(f"{url}/rest/v1/seo_outlines?select=id,keyword,status,research&status=neq.rejected",
                     headers=headers, timeout=60)
    if r.status_code >= 300:
        sys.exit(f"Không đọc được seo_outlines ({r.status_code}): {r.text[:300]}")

    done = skipped = missing = 0
    for o in r.json():
        f = reports.get(slugify(o["keyword"]))
        if not f:
            missing += 1
            print(f"  - {o['keyword']}: không có report.md trong seo_output")
            continue
        md = f.read_text(encoding="utf-8")
        research = dict(o.get("research") or {})
        if research.get("report_md") == md:
            skipped += 1
            continue
        research["report_md"] = md
        research["report_synced_at"] = datetime.now(timezone.utc).isoformat()
        print(f"  {'ghi' if apply else 'sẽ ghi'}: {o['keyword']}  <-  {f.parent.name}/report.md ({len(md)} ký tự)")
        if apply:
            p = requests.patch(f"{url}/rest/v1/seo_outlines?id=eq.{o['id']}", headers={**headers, "Prefer": "return=minimal"},
                               json={"research": research}, timeout=60)
            if p.status_code >= 300:
                sys.exit(f"Không ghi được outline {o['id']} ({p.status_code}): {p.text[:300]}")
        done += 1
    print(f"{'Đã ghi' if apply else 'Sẽ ghi'} {done} · đã đồng bộ sẵn {skipped} · thiếu report {missing}."
          + ("" if apply else "  Thêm --apply để ghi thật."))


if __name__ == "__main__":
    main()
