"""
Mini backend server phục vụ dữ liệu cũ từ file JSON cho demo giao diện.
Chạy: python backend/app.py
"""
import json
import os
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"
FRONTEND_DIR = BASE_DIR / "frontend"

REPORT_FILE = DATA_DIR / "latest_top10_report.json"


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        print(f"[{self.address_string()}] {fmt % args}")

    def send_cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_cors()
        self.end_headers()

    def do_GET(self):
        path = self.path.split("?")[0]

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


if __name__ == "__main__":
    port = 8000
    print(f"🚀 Demo server đang chạy tại: http://127.0.0.1:{port}")
    print(f"📂 Dữ liệu từ: {REPORT_FILE}")
    print("   Nhấn Ctrl+C để dừng.\n")
    HTTPServer(("127.0.0.1", port), Handler).serve_forever()
