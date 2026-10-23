# -*- coding: utf-8 -*-
"""
FastAPI Server cung cấp API và giao diện Web Dashboard cho hệ thống nghiên cứu Top 20 Keyword Tin tức Công nghệ.

Bảo mật: các endpoint ghi dữ liệu hoặc tốn lượt SerpApi (PATCH suggestions, refresh_news, force_serpapi)
- Nếu đặt TNC_API_TOKEN trong .env: yêu cầu header "X-API-Token" khớp.
- Nếu không đặt: chỉ cho phép request đến từ localhost.
CORS chỉ mở cho localhost (thêm origin khác qua TNC_CORS_ORIGINS, cách nhau dấu phẩy).
"""

import hmac
import json
import os
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse

from pydantic import BaseModel

from backend import db
from backend.engine import build_daily_top10_report
from backend.serpapi_client import DATA_DIR, get_serpapi_account_info

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent
FRONTEND_DIR = BASE_DIR / "frontend"
FRONTEND_DIR.mkdir(parents=True, exist_ok=True)

LOCAL_CLIENTS = {"127.0.0.1", "::1", "localhost"}
DEFAULT_CORS = ["http://localhost:8000", "http://127.0.0.1:8000"]
extra_origins = [o.strip() for o in os.getenv("TNC_CORS_ORIGINS", "").split(",") if o.strip()]

app = FastAPI(
    title="LỌC KEYWORD TIN TỨC CÔNG NGHỆ HOT",
    description="Hệ thống nghiên cứu Top 20 Keyword Tin tức Công nghệ & Top 5 Bài viết mỗi ngày",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=DEFAULT_CORS + extra_origins,
    allow_methods=["GET", "PATCH"],
    allow_headers=["Content-Type", "X-API-Token"],
)


def require_privileged(request: Request) -> None:
    """Chặn gọi ẩn danh vào endpoint ghi dữ liệu / tốn quota."""
    token = os.getenv("TNC_API_TOKEN", "").strip()
    if token:
        sent = request.headers.get("x-api-token", "")
        if not hmac.compare_digest(sent, token):
            raise HTTPException(status_code=401, detail="Thiếu hoặc sai X-API-Token")
        return
    client = request.client.host if request.client else ""
    if client not in LOCAL_CLIENTS:
        raise HTTPException(status_code=403, detail="Chỉ cho phép từ localhost; đặt TNC_API_TOKEN để mở từ xa")


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
    request: Request,
    hours: int = Query(48, ge=1, le=72, description="Khung thời gian quét tin tức (24 hoặc 48 giờ)"),
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
        except Exception as e:
            print(f"[app] Không đọc được báo cáo cache, sẽ tạo mới: {e}")

    require_privileged(request)
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
def patch_suggestion(suggestion_id: int, body: SuggestionUpdate, request: Request):
    require_privileged(request)
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
