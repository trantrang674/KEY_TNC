# -*- coding: utf-8 -*-
"""Nhập dữ liệu JSON cũ (serpapi_daily_*.json, latest_top10_report.json) vào data/tnc.db.
Chạy từ thư mục gốc:  python import_json_to_db.py
"""
import json
from pathlib import Path

from backend import db

DATA_DIR = Path(__file__).resolve().parent / "data"


def main() -> None:
    serp_ids = {}
    with db.session() as conn:
        for f in sorted(DATA_DIR.glob("serpapi_daily_*.json")):
            serp = json.loads(f.read_text(encoding="utf-8"))
            serp["from_cache"] = False
            run_id = db.save_serpapi(conn, serp)
            serp_ids[(serp.get("date") or "")[:10]] = run_id
            print(f"SerpApi {f.name}: run_id={run_id}")

        report_file = DATA_DIR / "latest_top10_report.json"
        if report_file.exists():
            report = json.loads(report_file.read_text(encoding="utf-8"))
            d, m, y = report["generated_at"][:10].split("/")
            run_id = db.save_report(conn, report, serp_ids.get(f"{y}-{m}-{d}"), triggered_by="import")
            db.save_quota(conn, report.get("serpapi_status", {}).get("account", {}))
            print(f"Báo cáo {report['generated_at']}: report_run_id={run_id}")


if __name__ == "__main__":
    main()
