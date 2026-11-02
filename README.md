# KEY_TNC – Nghiên cứu Top 20 Keyword Tin Công Nghệ & Quản lý SEO Workflow

Hệ thống tự động quét 16 nguồn RSS báo công nghệ VN, đối thủ & Google News (48h), gom cụm và phân loại 9 ngách nội dung (loại trừ smartphone Android nhưng giữ bài PC/Laptop, sự kiện Apple và thủ thuật hot), làm giàu bằng 4 cổng SerpApi (1 lượt/cổng/ngày, cache 24h), chấm điểm thang 100 (`coverage` 40 + `competitor` 25 + `freshness` 20 + `serpapi_trend` 15) và xuất **Top 20 keyword** (mỗi keyword gồm **Top 5 bài viết** + **tối đa 3 gợi ý keyword viết bài SEO**).

Đi kèm **Web Dashboard 6 tab** trên GitHub Pages (đăng nhập Supabase Auth) để:
1. Xem báo cáo Top 20 Keyword theo ngày & cột Google Trending Now (VN).
2. **Duyệt 3 bước với Cowork** (Duyệt Keyword $\rightarrow$ Duyệt Outline $\rightarrow$ Duyệt Bài viết + tự tạo Google Docs + chuông thông báo).
3. **Đo lường hiệu quả bài viết bằng Google Search Console + GA4** và phát hiện bài cần làm mới (`NÊN LÀM MỚI`).

> 📖 Xem sơ đồ kiến trúc và luồng vận hành chi tiết tại [`docs/README_SO_DO_HE_THONG.md`](docs/README_SO_DO_HE_THONG.md) và cấu hình Cowork tại [`cowork/COWORK_TASK.md`](cowork/COWORK_TASK.md).

---

## 1. Chạy cục bộ (trong thư mục `KEY_TNC/`)

```powershell
pip install -r requirements.txt

# Quét mới + đẩy báo cáo lên Supabase + báo Zalo + dựng site/index.html
python build_static.py

# Dùng lại data/latest_top10_report.json (không tốn SerpApi, KHÔNG ghi đè lên Supabase)
python build_static.py --reuse

# Chỉ xuất lại giao diện site/index.html (không chạy engine, không ghi báo cáo)
python build_static.py --ui-only

# Xem thử Dashboard tĩnh tại http://127.0.0.1:8080
python -m http.server -d site 8080

# Đồng bộ số liệu GSC + GA4 và đồng bộ bù report.md của Cowork
python sync_gsc_ga4.py --apply
python sync_reports.py --apply

# Chạy bộ kiểm thử (test_core.py & test_suggester.py)
python -m unittest discover -s tests -v
```

## 2. Biến môi trường & GitHub Secrets

Tạo file `.env` (không commit) hoặc cấu hình trong **GitHub Secrets**:
- Bắt buộc khi quét & dựng trang: `SERPAPI_API_KEY`, `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_KEY`
- Báo Zalo Bot (tùy chọn): `ZALO_BOT_TOKEN`, `ZALO_CHAT_ID`
- Đồng bộ GSC + GA4: `GOOGLE_SERVICE_ACCOUNT_JSON` (hoặc đường dẫn file JSON cục bộ)

## 3. Cơ sở dữ liệu & Bảo mật (Supabase)

- Chạy các file SQL trong [`database/`](database/) trên Supabase SQL Editor:
  - Đăng nhập & phân quyền: `auth_postgres.sql`, `admin_only_users.sql` (**bắt buộc tắt "Allow new users to sign up"** trong Supabase Dashboard).
  - Quy trình duyệt & Cowork: `approved_keywords.sql`, `seo_content.sql`, `seo_articles_google_doc.sql`, `cowork_notifications.sql`, `cowork_heartbeat.sql`.
  - Đo lường & Zalo: `seo_article_metrics.sql`, `zalo_messages.sql`.
- Edge Functions trong [`supabase/functions/`](supabase/functions/): `cowork-api` (xác thực bằng `x-api-key: $COWORK_API_KEY`) và `zalo-webhook` (nhận lệnh `/quet`, `/top`).

## 4. Lịch chạy tự động (Giờ Việt Nam)

| Tác vụ | Nơi chạy | Lịch chạy |
|---|---|---|
| Quét tin + dựng GitHub Pages | GitHub Actions [`daily-pages.yml`](.github/workflows/daily-pages.yml) | **12:00** thứ 2, 4, 6; bấm chạy tay (có cờ `ui_only`); hoặc nhắn `/quet` trên Zalo |
| Đồng bộ GSC + GA4 | GitHub Actions [`sync-gsc-ga4.yml`](.github/workflows/sync-gsc-ga4.yml) | **06:00, 12:00, 18:00** mỗi ngày (không tốn token AI) |
| Cowork lập outline + viết bài | Máy cục bộ (`tnc-seo-content`) | **10:00** mỗi ngày (xem [`cowork/COWORK_TASK.md`](cowork/COWORK_TASK.md)) |

## 5. Lưu ý thiết kế

- **Tiêu chuẩn gợi ý Keyword SEO (`backend/seo_suggester.py`):** Chỉ sinh keyword là sự kiện/chủ đề cụ thể viết được thành bài (`<thực thể> + sự việc`), không độn cụm chung chung (`mới nhất`, `đánh giá`, `hướng dẫn`...), không để từ lửng cuối câu. Tên người gắn với sự kiện được phép dài tới 12 từ.
- **Nhóm "Có thể quan tâm" (`BIG_TECH_EVENT`):** Luôn xếp dưới các nhóm ngành trọng tâm khác trong Top 20.
- **Giới hạn quota SerpApi:** Điểm `serpapi_trend` chỉ đo Google Trends thật cho 5 ứng viên đầu (1 lượt gộp tối đa 5 từ khóa); các keyword còn lại nhận điểm nền và điểm Trending Now.
- **Độ tươi bài Google Search:** Chỉ tính "tươi" khi đọc được ngày đăng; không đọc được thì coi là ~36h.
- **Tương thích dữ liệu:** Tên khóa JSON `top_10_keywords` / `top_3_articles` và file `data/latest_top10_report.json` được giữ nguyên để tương thích dữ liệu cũ, nhưng thực tế chứa **20 keyword / 5 bài**.
