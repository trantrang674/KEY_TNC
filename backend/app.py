# -*- coding: utf-8 -*-
"""
FastAPI Server cung cấp API và giao diện Web Dashboard cho hệ thống nghiên cứu Top 10 Keyword Tin tức Công nghệ.
"""

import json
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles

from backend.engine import build_daily_top10_report
from backend.serpapi_client import DATA_DIR, get_serpapi_account_info

BASE_DIR = Path(__file__).resolve().parent.parent
FRONTEND_DIR = BASE_DIR / "frontend"
FRONTEND_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(
    title="LỌC KEYWORD TIN TỨC CÔNG NGHỆ HOT",
    description="Hệ thống nghiên cứu Top 10 Keyword Tin tức Công nghệ & Top 3 Bài viết mỗi ngày",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/", response_class=HTMLResponse)
def serve_dashboard():
    index_file = FRONTEND_DIR / "index.html"
    if index_file.exists():
        return index_file.read_text(encoding="utf-8")
    return "<h1>Dashboard đang được khởi tạo...</h1>"


@app.get("/logo.png")
def serve_logo():
    logo_file = FRONTEND_DIR / "logo.png"
    if logo_file.exists():
        return FileResponse(logo_file, media_type="image/png")
    return JSONResponse(status_code=404, content={"error": "Logo not found"})


@app.get("/api/report")
def get_report(
    hours: int = Query(48, description="Khung thời gian quét tin tức (24 hoặc 48 giờ)"),
    refresh_news: bool = Query(False, description="Quét lại nguồn tin tức RSS mới nhất"),
    force_serpapi: bool = Query(False, description="Bắt buộc gọi mới 4 cổng SerpApi (tốn 4 lượt)")
):
    latest_report_path = DATA_DIR / "latest_top10_report.json"

    if not refresh_news and not force_serpapi and latest_report_path.exists():
        try:
            with open(latest_report_path, "r", encoding="utf-8") as f:
                cached_report = json.load(f)
                # Cập nhật thông tin quota mới nhất (miễn phí)
                cached_report["serpapi_status"]["account"] = get_serpapi_account_info()
                return JSONResponse(content=cached_report)
        except Exception:
            pass

    report = build_daily_top10_report(max_hours=hours, force_serpapi=force_serpapi)
    return JSONResponse(content=report)


@app.get("/api/quota")
def get_quota():
    return JSONResponse(content=get_serpapi_account_info())
