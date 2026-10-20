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

from pydantic import BaseModel

from backend import db
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


@app.get("/api/history")
def get_keyword_history(keyword: str = Query(..., description="Tên keyword (khớp một phần)"),
                        limit: int = Query(30, le=200)):
    return JSONResponse(content=db.keyword_history(keyword, limit))


@app.get("/api/suggestions")
def get_suggestions(status: Optional[str] = Query(None, description="NEW|PLANNED|WRITING|PUBLISHED|SKIPPED"),
                    limit: int = Query(100, le=500)):
    return JSONResponse(content=db.list_suggestions(status, limit))


class SuggestionUpdate(BaseModel):
    status: Optional[str] = None
    assignee: Optional[str] = None
    published_url: Optional[str] = None
    note: Optional[str] = None


@app.patch("/api/suggestions/{suggestion_id}")
def patch_suggestion(suggestion_id: int, body: SuggestionUpdate):
    try:
        ok = db.update_suggestion(suggestion_id, body.model_dump(exclude_none=True))
    except ValueError as e:
        return JSONResponse(status_code=400, content={"error": str(e)})
    if not ok:
        return JSONResponse(status_code=404, content={"error": "Không tìm thấy gợi ý"})
    return {"ok": True}


@app.get("/api/quota")
def get_quota():
    return JSONResponse(content=get_serpapi_account_info())
