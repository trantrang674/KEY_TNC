"""
Mini backend server phục vụ dữ liệu cũ từ file JSON cho demo giao diện và API workflow bài viết.
Chạy: python backend/app.py
"""
import json
import os
import urllib.parse
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"
FRONTEND_DIR = BASE_DIR / "frontend"

REPORT_FILE = DATA_DIR / "latest_top10_report.json"
WORKFLOW_FILE = DATA_DIR / "workflow.json"


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        print(f"[{self.address_string()}] {fmt % args}")

    def send_cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_cors()
        self.end_headers()

    def do_GET(self):
        parts = self.path.split("?", 1)
        path = parts[0]
        query = parts[1] if len(parts) > 1 else ""

        # ── API: /api/report ──────────────────────────────────────────────
        if path == "/api/report":
            try:
                data = json.loads(REPORT_FILE.read_text(encoding="utf-8"))
                body = json.dumps(data, ensure_ascii=False).encode("utf-8")
                self.send_response(200)
                self.send_cors()
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", len(body))
                self.end_headers()
                self.wfile.write(body)
            except Exception as e:
                self.send_error(500, str(e))
            return

        # ── API: /api/workflow ───────────────────────────────────────────
        if path == "/api/workflow":
            try:
                data = {}
                if WORKFLOW_FILE.exists():
                    data = json.loads(WORKFLOW_FILE.read_text(encoding="utf-8"))
                body = json.dumps(data, ensure_ascii=False).encode("utf-8")
                self.send_response(200)
                self.send_cors()
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", len(body))
                self.end_headers()
                self.wfile.write(body)
            except Exception as e:
                self.send_error(500, str(e))
            return

        # ── API: /api/article?file=... ───────────────────────────────────
        if path == "/api/article":
            try:
                params = urllib.parse.parse_qs(query)
                file_rel = params.get("file", [""])[0]
                if not file_rel:
                    raise ValueError("Thiếu tham số file")
                target = (BASE_DIR / file_rel.lstrip("/\\")).resolve()
                if not str(target).startswith(str(BASE_DIR.resolve())):
                    raise PermissionError("Không được phép truy cập ngoài thư mục dự án")
                if not target.exists():
                    raise FileNotFoundError(f"Không tìm thấy file: {file_rel}")
                content = target.read_text(encoding="utf-8")
                resp_data = {"file": file_rel, "content": content}
                body = json.dumps(resp_data, ensure_ascii=False).encode("utf-8")
                self.send_response(200)
                self.send_cors()
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", len(body))
                self.end_headers()
                self.wfile.write(body)
            except Exception as e:
                self.send_error(400, str(e))
            return

        # ── Static files từ thư mục frontend ─────────────────────────────
        if path == "/":
            path = "/index.html"

        file_path = FRONTEND_DIR / path.lstrip("/")
        if file_path.exists() and file_path.is_file():
            ext = file_path.suffix.lower()
            content_types = {
                ".html": "text/html; charset=utf-8",
                ".css":  "text/css",
                ".js":   "application/javascript",
                ".png":  "image/png",
                ".ico":  "image/x-icon",
                ".json": "application/json",
            }
            content_type = content_types.get(ext, "application/octet-stream")
            body = file_path.read_bytes()
            self.send_response(200)
            self.send_cors()
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", len(body))
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_error(404, f"Not found: {path}")

    def do_POST(self):
        path = self.path.split("?")[0]
        content_len = int(self.headers.get("Content-Length", 0))
        raw_body = self.rfile.read(content_len)

        # ── API: Cập nhật workflow /api/workflow ─────────────────────────
        if path == "/api/workflow":
            try:
                data = json.loads(raw_body.decode("utf-8"))
                DATA_DIR.mkdir(parents=True, exist_ok=True)
                WORKFLOW_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
                resp = json.dumps({"status": "ok", "count": len(data)}, ensure_ascii=False).encode("utf-8")
                self.send_response(200)
                self.send_cors()
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", len(resp))
                self.end_headers()
                self.wfile.write(resp)
            except Exception as e:
                self.send_error(400, str(e))
            return

        # ── API: Lưu bài viết .md /api/article ───────────────────────────
        if path == "/api/article":
            try:
                payload = json.loads(raw_body.decode("utf-8"))
                file_rel = payload.get("file", "").strip()
                content = payload.get("content", "")
                if not file_rel:
                    file_rel = "outputs/articles/article.md"
                target = (BASE_DIR / file_rel.lstrip("/\\")).resolve()
                if not str(target).startswith(str(BASE_DIR.resolve())):
                    raise PermissionError("Không được phép ghi ngoài thư mục dự án")
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(content, encoding="utf-8")
                resp = json.dumps({"status": "ok", "file": file_rel}, ensure_ascii=False).encode("utf-8")
                self.send_response(200)
                self.send_cors()
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", len(resp))
                self.end_headers()
                self.wfile.write(resp)
            except Exception as e:
                self.send_error(400, str(e))
            return

        self.send_error(404, "Endpoint không hỗ trợ")


if __name__ == "__main__":
    port = 8000
    print(f"🚀 Demo server đang chạy tại: http://127.0.0.1:{port}")
    print(f"📂 Dữ liệu từ: {REPORT_FILE}")
    print("   Nhấn Ctrl+C để dừng.\n")
    HTTPServer(("127.0.0.1", port), Handler).serve_forever()
