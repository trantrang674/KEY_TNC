# KEY_TNC – Nghiên cứu Top 20 keyword tin công nghệ

Quét RSS báo công nghệ và đối thủ (48h), gom cụm keyword, làm giàu bằng 4 API SerpApi (1 lượt/API/ngày, cache theo ngày),
chấm điểm thang 100 (độ phủ 40, đối thủ 25, độ mới 20, SerpApi 15) và xuất Top 20 keyword, mỗi keyword 5 bài + 3 gợi ý SEO.

## Chạy cục bộ
```
pip install -r requirements.txt
python run_dashboard.py          # http://localhost:8000
python -m unittest discover -s tests -v
```
Tạo `.env` (không commit): `SERPAPI_API_KEY`, `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_KEY`, tuỳ chọn `TNC_API_TOKEN`, `TNC_CORS_ORIGINS`.

## Bảo mật API
- `PATCH /api/suggestions/*`, `?refresh_news=true`, `?force_serpapi=true` (tốn 4 lượt SerpApi) chỉ chấp nhận từ localhost,
  hoặc request có header `X-API-Token` khớp `TNC_API_TOKEN`.
- CORS chỉ mở cho localhost (thêm origin qua `TNC_CORS_ORIGINS`).
- Trang tĩnh GitHub Pages dùng Supabase Auth: chạy `database/auth_postgres.sql` rồi `database/admin_only_users.sql`,
  và **bắt buộc tắt "Allow new users to sign up"** trong Supabase Dashboard.

## GitHub Actions
`daily-pages.yml` chỉ chạy tay. Runner không có `data/tnc.db` nên mỗi lần chạy tạo SQLite mới; lịch sử dài hạn
lấy từ bảng `daily_reports` trên Supabase, còn lịch sử chi tiết (`push_to_supabase.py`) chỉ có khi chạy ở máy cục bộ.

## Lưu ý thiết kế
- Điểm `serpapi_trend` chỉ đo thật cho 5 ứng viên đầu (giới hạn quota: 1 lượt Google Trends gộp tối đa 5 từ khóa);
  các keyword còn lại chỉ nhận điểm nền và điểm Trending Now.
- Bài từ Google Search chỉ được tính "tươi" khi đọc được ngày đăng; không đọc được thì coi là ~36h.
- Tên khóa JSON `top_10_keywords` / `top_3_articles` giữ nguyên để tương thích dữ liệu cũ, nhưng thực chứa 20 keyword / 5 bài.
