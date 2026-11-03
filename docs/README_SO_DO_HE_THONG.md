# TÀI LIỆU SƠ ĐỒ HỆ THỐNG TNC SEO KEYWORD NEWS (KEY_TNC)

Phiên bản 3.0, cập nhật 31/10/2026. Thay đổi lớn nhất so với bản cũ: **Cowork chạy cục bộ** (lập outline, viết bài, tạo Google Docs), chuông thông báo trên Dashboard, và **đo hiệu quả bài bằng Google Search Console + GA4**.

---

## 📌 Các file sơ đồ trong thư mục này

| File | Dùng để |
|---|---|
| [`he_thong_tnc_seo_architecture.html`](he_thong_tnc_seo_architecture.html) | Sơ đồ tương tác (mở bằng trình duyệt, có nút In / Lưu PDF) |
| [`infographic_agent_tnc.html`](infographic_agent_tnc.html) | Infographic dạng poster của hệ thống Agent |
| [`SO_DO_HE_THONG_TNC_SEO.pdf`](SO_DO_HE_THONG_TNC_SEO.pdf) / [`.png`](SO_DO_HE_THONG_TNC_SEO.png) | Bản xuất sẵn của sơ đồ hệ thống (gửi Zalo, in ấn) |
| [`SO_DO_INFOGRAPHIC_AGENT_TNC.pdf`](SO_DO_INFOGRAPHIC_AGENT_TNC.pdf) / [`.png`](SO_DO_INFOGRAPHIC_AGENT_TNC.png) | Bản xuất sẵn của infographic |

---

## 🗺️ 1. Kiến trúc tổng thể

```mermaid
flowchart LR
    subgraph SRC ["NGUỒN DỮ LIỆU"]
        RSS["16 nguồn RSS / Google News<br/>+ 4 cổng SerpApi"]
        GOOGLE["Google Search Console + GA4<br/>+ trang Tin tức tnc.com.vn"]
    end

    subgraph GH ["GITHUB ACTIONS"]
        GHA1["daily-pages.yml<br/>12:00 T2-T4-T6 hoặc /quet<br/>build_static.py + engine.py"]
        GHA2["sync-gsc-ga4.yml<br/>6h / 12h / 18h<br/>sync_gsc_ga4.py"]
    end

    subgraph SB ["SUPABASE"]
        DB[("Database<br/>daily_reports, approved_keywords<br/>seo_outlines, seo_articles<br/>seo_article_metrics<br/>cowork_notifications<br/>cowork_heartbeat")]
        CAPI["cowork-api<br/>x-api-key"]
        ZF["zalo-webhook"]
    end

    subgraph USERS ["NGƯỜI DÙNG"]
        DASH["Dashboard GitHub Pages<br/>6 tab + chuông"]
        ZALO["Zalo Bot"]
        WEB["tnc.com.vn<br/>đăng bài thật"]
    end

    subgraph LOCAL ["MÁY CHẠY COWORK"]
        COWORK["Cowork 10h sáng<br/>tnc-seo-content"]
        GDOCS["Google Docs"]
    end

    RSS --> GHA1
    GHA1 -->|ghi báo cáo| DB
    GHA1 -->|dựng site| DASH
    GHA1 -->|Top 3| ZALO
    GOOGLE --> GHA2
    GHA2 -->|ghi số liệu| DB
    DASH <-->|đọc, duyệt| DB
    COWORK <--> CAPI
    CAPI <--> DB
    COWORK --> GDOCS
    ZF --> ZALO
    ZALO -->|/quet| ZF
    ZF -->|dispatch| GHA1
    GDOCS -.->|người đăng| WEB
    DASH -.->|dán link bài| DB
```

---

## ⏰ 2. Ai chạy khi nào (giờ Việt Nam)

| Tác vụ | Chạy ở đâu | Lịch | Cách kiểm tra |
|---|---|---|---|
| Quét tin + chấm điểm | GitHub Actions `daily-pages.yml` | 12:00 thứ 2, 4, 6; chạy tay; hoặc `/quet` trên Zalo | Tab Actions xanh; Dashboard hiện "Cập nhật lần cuối" đúng giờ |
| Cowork lập outline + viết bài | Máy chạy Cowork (scheduled task) | 10:00 mỗi ngày (`0 10 * * *`) | Dòng "Cowork chạy lần cuối" trên Dashboard (đỏ nếu quá 26 giờ hoặc báo lỗi) |
| Đồng bộ GSC + GA4 | GitHub Actions `sync-gsc-ga4.yml` | 6:00, 12:00, 18:00 mỗi ngày | Cột `synced_at`, `data_end_date` trong `seo_article_metrics` |
| Lệnh Zalo | `zalo-webhook` | Khi nhắn `/quet` hoặc `/top` | Bot trả lời "Đã gọi quét" hoặc lỗi GitHub |

---

## 📂 3. Nhiệm vụ từng file & thư mục

### `backend/` (xử lý dữ liệu, chấm điểm)
- `engine.py`: nhạc trưởng. Chấm 100 điểm, chọn **Top 20 keyword**, mỗi keyword 5 bài + 3 gợi ý. Nhóm "Có thể quan tâm" luôn xếp cuối.
- `news_fetcher.py`: quét **16 nguồn** RSS / Google News trong 48h (báo công nghệ, shop đối thủ, Google News theo chủ đề AI, game, chính sách số).
- `classifier.py`: gán 1 trong **9 nhóm chủ đề** (Linh kiện - Phần cứng, HĐH - Phần mềm, Có thể quan tâm, Game, A.I, Mạng xã hội - App, Chính sách - Quy định, An ninh mạng, Tối ưu - Sửa lỗi), nhận diện brand, và lọc bỏ mảng smartphone Android (nhưng giữ lại bài có yếu tố PC/Laptop, sự kiện từ Apple và thủ thuật hot).
- `serpapi_client.py`: 4 cổng SerpApi, mỗi cổng 1 lượt/ngày, cache `data/serpapi_daily_*.json`. Gói Free có 250 lượt/tháng; mỗi lần quét tốn 4 lượt.
- `seo_suggester.py`: sinh tối đa 3 gợi ý keyword viết bài SEO bám sát sự kiện/vấn đề trong Top 5 bài viết (loại cụm chung chung, loại từ lửng cuối câu, hỗ trợ keyword dài tới 12 từ cho tên người gắn với sự kiện).

### `frontend/`, `data/`, `site/`
- `frontend/index.html`: Dashboard 1 trang, **6 tab**: Dashboard Keyword, Keyword Duyệt, Workflow, Báo cáo, Đề xuất, **Cài đặt**. Tab Báo cáo có khung "Bài cần xử lý" nằm cạnh biểu đồ (giảm clicks, tụt hạng, CTR thấp, chưa index; so 14 ngày gần nhất với 14 ngày trước, bỏ ngày cuối; phân trang 3 bài/trang; bài Cowork ★ luôn xếp trước và có nút lọc Tất cả nguồn / Bài Cowork / Bài khác; bài giảm clicks hoặc tụt hạng được đánh dấu NÊN LÀM MỚI). Bảng đo lường hiệu năng mặc định xếp "Bài mới nhất (ngày xuất bản)", không còn cột Audit. Menu trái là dải màu tím đậm. Tab Cài đặt là thẻ sức khỏe hệ thống (lần quét, lần sync GSC+GA4, Cowork, lượt SerpApi). Có chuông thông báo của Cowork và dòng "Cowork chạy lần cuối".
- `data/latest_top10_report.json`: báo cáo mới nhất ghi trên máy chạy (tên giữ cũ nhưng chứa 20 keyword).
- `site/`: bản tĩnh sinh tự động để đăng GitHub Pages (không commit).

### `database/` (chạy trong Supabase SQL Editor)
- `auth_postgres.sql`, `admin_only_users.sql`: đăng nhập; chỉ tài khoản được duyệt mới đọc `daily_reports`.
- `seo_content.sql`: `seo_outlines`, `seo_articles` (có ghi chú góp ý `review_note`, link bài đã đăng `published_url`).
- `approved_keywords.sql`: keyword đã duyệt.
- `cowork_notifications.sql`, `cowork_heartbeat.sql`: chuông thông báo và nhịp hoạt động của Cowork.
- `seo_articles_google_doc.sql`: cột link Google Docs.
- `seo_article_metrics.sql`: số liệu GSC + GA4 từng bài.
- `zalo_messages.sql`: bảng log tin Zalo.

### `supabase/functions/` (Edge Functions)
- `cowork-api`: API cho Cowork, xác thực bằng `x-api-key`: `GET /keywords`, `POST /outlines`, `GET /outlines/approved`, `POST /articles`, `POST /notifications`, `POST /heartbeat`, `GET /refresh-candidates` (bài nên làm mới, tối đa 10 bài).
- `zalo-webhook`: nhận tin Zalo; lệnh `/quet` (gọi GitHub chạy quét) và `/top`. Chỉ nhận lệnh từ đúng `ZALO_CHAT_ID`.

### `cowork/`, `.github/`, file ở thư mục gốc
- `cowork/COWORK_TASK.md`: hướng dẫn cài đặt và prompt của scheduled task Cowork chạy tại `tnc-seo-content` (sử dụng 2 bộ skill `tnc-viet-bai-tin` và `tnc-viet-bai-review`, kiểm soát chất lượng bằng Bộ 13 Tiêu chí Chấm điểm SEO trong `cham-diem-seo.md` và `evaluate_seo.py` đạt $\ge$ 90 điểm).
- `.github/workflows/daily-pages.yml`: quét + dựng GitHub Pages.
- `.github/workflows/sync-gsc-ga4.yml`: đồng bộ GSC + GA4 (không tốn token AI).
- `build_static.py`: quét, đẩy báo cáo, báo Zalo, dựng `site/`. `--ui-only` chỉ dựng giao diện; `--reuse` dựng lại từ file local và **không ghi lên Supabase**.
- `sync_gsc_ga4.py`: (ngày cuối dữ liệu `data_end_date` = ngày GSC thật sự có số, không phải hôm nay) kéo GSC + GA4 cho bài trong 60 ngày của danh mục Tin tức và bài của dashboard.
- `sync_reports.py`: đồng bộ bù `report.md` từ `seo_output` lên Supabase.
- `tests/test_core.py`, `tests/test_suggester.py`: bộ kiểm thử khớp keyword, độ tươi, bộ lọc smartphone đã nới và tiêu chuẩn gợi ý keyword SEO.
- `.env`: khóa bí mật (không commit). GitHub Secrets cần có: `SERPAPI_API_KEY`, `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_KEY`, `ZALO_BOT_TOKEN`, `ZALO_CHAT_ID`, `GOOGLE_SERVICE_ACCOUNT_JSON`.

---

## ⚡ 4. Chu kỳ vận hành end-to-end

Người duyệt 3 lần (keyword, outline, bài). **Cowork không bao giờ tự duyệt.**

```mermaid
sequenceDiagram
    autonumber
    actor Editor as Biên tập viên
    participant GH as GitHub Actions
    participant UI as Dashboard
    participant SB as Supabase
    participant ZL as Zalo Bot
    participant CW as Cowork (máy cục bộ)
    participant GD as Google Docs
    participant G as GSC + GA4

    Note over GH,ZL: Giai đoạn 1: Quét tin
    GH->>SB: Ghi báo cáo Top 20 keyword vào daily_reports
    GH->>ZL: Báo Top 3 keyword + link Dashboard
    Editor->>UI: Xem báo cáo, bấm Duyệt đẩy Cowork
    UI->>SB: Lưu approved_keywords

    Note over CW,SB: Giai đoạn 2: Cowork lập outline (10h sáng)
    CW->>SB: heartbeat running, GET keywords (tối đa 5)
    CW->>CW: Phân tích đối thủ, chọn 4-6 key phụ, lập outline, FAQ 5 câu
    CW->>SB: POST outlines (kèm report.md), chờ duyệt
    Editor->>UI: Duyệt outline hoặc Từ chối kèm góp ý
    UI->>SB: status approved / rejected + review_note

    Note over CW,GD: Giai đoạn 3: Cowork viết bài
    CW->>SB: GET outlines/approved (tối đa 5, kèm góp ý nếu bài bị từ chối)
    CW->>CW: Viết 1.500-2.200 từ, evaluate_seo.py đạt 90 trở lên, meta 150-160 ký tự
    CW->>GD: Tạo Google Docs trong thư mục Drive của TNC
    CW->>SB: POST articles (kèm google_doc_url), chờ duyệt
    CW->>SB: POST notifications (chuông) + heartbeat ok
    Editor->>UI: Duyệt bài hoặc Từ chối kèm góp ý (Cowork viết lại lần sau)

    Note over Editor,G: Giai đoạn 4: Đăng bài và đo hiệu quả
    Editor->>Editor: Lấy bài từ Google Docs, đăng lên tnc.com.vn
    Editor->>UI: Dán link bài đã đăng (published_url)
    GH->>G: Đồng bộ 6h, 12h, 18h
    G-->>SB: Clicks, impressions, vị trí, query, GA4, trạng thái index
    Editor->>UI: Tab BÁO CÁO xem bài lên hạng chưa, mục Bài cần xử lý
    CW->>SB: GET refresh-candidates (bài giảm clicks hoặc tụt hạng)
    CW->>SB: POST notifications, gợi ý làm mới (0 tốn SerpApi: chỉ phân tích On-page cục bộ, không tự sửa bài)
    Editor->>UI: Tab CÀI ĐẶT xem sức khỏe: quét, sync, Cowork, SerpApi
```

**Quy tắc của Cowork** (theo `cowork/COWORK_TASK.md`): mỗi lần chạy tối đa 5 keyword và 5 outline; Phần C chỉ **đề xuất** làm mới tối đa 3 bài cũ qua chuông (hoàn toàn **0 tốn lượt SerpApi**: chạy `refresh_audit.py` đọc lý do GSC từ Supabase, chấm lại 13 tiêu chí và lưu báo cáo vào thư mục riêng `seo_output/<slug>/seo_audit/`, tuyệt đối không gọi `serp_keyword.py` hay SerpApi; không tự sửa bài); dùng đúng 100% key phụ trong outline đã duyệt; bài viết phải đạt điểm SEO ≥ 90/100 theo Bộ 13 tiêu chí chuẩn; không để link trong bài; không dùng em-dash "—"; gặp mã 409 (đã có) thì bỏ qua; lỗi tạo Google Docs hoặc gửi thông báo không làm dừng cả lần chạy.

---

## 🎯 5. Công thức chấm điểm từ khóa & Tiêu chuẩn chất lượng bài viết

### 5.1. Chấm điểm từ khóa Hot hàng ngày (thang 100)

Tại `backend/engine.py`:

| Tiêu chí | Điểm | Ý nghĩa |
|---|---|---|
| **Độ phủ báo chí** | **40** | Nhiều báo cùng đưa tin trong 24-48h thì chủ đề càng nóng. |
| **Đối thủ đã viết** | **25** | GearVN, CellphoneS, Phong Vũ, FPT Shop, Thế Giới Di Động... đã lên bài. |
| **Độ tươi mới** | **20** | Tin dưới 6 giờ được điểm tối đa, giảm dần theo tuổi tin. |
| **Xác thực SerpApi** | **15** | Trending Now và Google Trends (chỉ đo thật cho 5 ứng viên đầu do giới hạn quota). |

### 5.2. Bộ 13 Tiêu chuẩn Chấm điểm SEO cho Bài viết (Thang 100, nghiệm thu ≥ 90)

Kiểm soát tự động qua `evaluate_seo.py` và chuẩn hóa tại `cham-diem-seo.md` (áp dụng cho cả bài Tin tức `tnc-viet-bai-tin` và bài Review `tnc-viet-bai-review`):

| # | Tiêu chí | Trọng số | Khoảng chuẩn nghiệm thu |
|---|---|:---:|---|
| 1 | **Tiêu đề (Title)** | 12 | 50 ≤ len ≤ 60 ký tự, chứa từ khóa chính, không có dấu chấm cuối. |
| 2 | **Meta description** | 8 | 150 ≤ len ≤ 160 ký tự, từ khóa chính ngay đầu câu, không có link. |
| 3 | **Mật độ từ khóa chính** | 10 | 0.8% - 1.2%, xuất hiện trong 100 từ đầu, ít nhất 2 thẻ H2 và phần Kết luận. |
| 4 | **Mật độ từ khóa phụ** | 8 | 4 - 6 từ khóa phụ (2-3 key ngắn + 2-3 key dài), mỗi từ lặp 2 - 5 lần. |
| 5 | **Độ dài tổng từ** | 10 | 1500 ≤ words ≤ 2200 từ thân bài. |
| 6 | **Heading (H2/H3)** | 10 | H2 ≥ 70 từ, H3 ≥ 50 từ (nếu có H3 thì ≥ 2 thẻ H3/H2), Sentence case. |
| 7 | **Đoạn mở đầu (Opening)** | 6 | 1 đoạn văn chuẩn (3-5 câu), từ khóa chính ở đầu câu, không in đậm, không link. |
| 8 | **Readability (Độ dễ đọc)** | 8 | Câu văn súc tích, độ dài câu trung bình ≤ 20 từ/câu, Flesch-Kincaid ≥ 60. |
| 9 | **Hình ảnh** | 6 | Tỉ lệ 3:2, 900x600 px; bài tin ≥ 2 hình, bài review ≥ 5 hình (mỗi H2 có 1 ảnh). |
| 10 | **Độc bản & Cấm link** | 10 | Không trùng > 30% đối thủ, cấm từ sáo rỗng mục 3.7, tuyệt đối cấm link trong bài. |
| 11 | **Không dùng em-dash** | 2 | Không xuất hiện dấu gạch ngang dài `—` trong toàn bài. |
| 12 | **FAQ (PAA)** | 5 | Đúng 5 câu hỏi - trả lời từ Google PAA, mỗi câu trả lời súc tích ≤ 80 từ. |
| 13 | **Kết luận & CTA** | 5 | Thẻ `## Kết luận` ≥ 70 từ; theo dõi Tin tức TNC (tin) hoặc CTA Showroom/Hotline 1900 6078 (review). |
| **Tổng** | **ĐẠT CHUẨN** | **100** | **Tổng điểm chấm bằng `evaluate_seo.py` phải đạt từ 90/100 điểm trở lên.** |

---

## 🛠️ 6. Khi nghi ngờ có chỗ không chạy

| Triệu chứng | Kiểm tra | Thường do |
|---|---|---|
| Dashboard hiện giờ cập nhật cũ | Tab Actions có run xanh của `daily-pages`? Bảng `daily_reports` dòng hôm nay, cột `updated_at` | Chạy tay `build_static.py` trên máy ghi đè (nay `--reuse` đã không ghi nữa); hoặc chạy chế độ chỉ giao diện |
| Cowork không ra outline / bài | Dòng "Cowork chạy lần cuối" và chuông trên Dashboard | Máy tắt lúc 10h, thiếu `COWORK_API_KEY` trong `.env`, hoặc chưa duyệt keyword / outline |
| Không thấy nút XEM REPORT | Outline có `research.report_md` chưa? | Chạy `python sync_reports.py --apply` |
| Số liệu BÁO CÁO chưa có / lệch | `seo_article_metrics`: `synced_at`, `data_end_date`; bài đã dán `published_url` chưa | Chưa dán link bài; Google trễ 1-2 ngày; bài chưa được index |
| Zalo không báo | Secret `ZALO_BOT_TOKEN`, `ZALO_CHAT_ID`; nhật ký `zalo-webhook` | Sai chat id, token hết hạn |
| Không rõ tác vụ nào đang trễ | Tab **Cài đặt** trên Dashboard: 4 thẻ (quét tin, sync GSC+GA4, Cowork, SerpApi); đỏ hoặc vàng là cần xử lý | Xem hướng dẫn xử lý ngay dưới các thẻ |
| Hết lượt SerpApi | Ô quota trên Dashboard (còn bao nhiêu / 250) | Chạy tay quá nhiều; mỗi lần quét tốn 4 lượt |
