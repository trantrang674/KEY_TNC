# Cowork: tự động lập outline và viết bài từ keyword đã duyệt

Chạy 1 lần/ngày. Thư mục làm việc của task phải là `C:\Users\MK01\Documents\GEMNI ANTIGRAVITY\tnc-seo-content`
(nơi có skill `tnc-seo-content`, `seo-keyword-research`, `evaluate_seo.py` và `.env` chứa SerpApi key).

## Cài đặt một lần
1. Supabase SQL Editor (project TNC): chạy `database/seo_content.sql`.
2. Đặt khóa API cho Cowork (chuỗi ngẫu nhiên dài, giữ bí mật):
   ```
   supabase secrets set COWORK_API_KEY=<chuoi-bi-mat> --project-ref lfexppnvvkqzygbwqnkv
   supabase functions deploy cowork-api --no-verify-jwt --project-ref lfexppnvvkqzygbwqnkv
   ```
3. Thêm vào `.env` của thư mục `tnc-seo-content`:
   ```
   COWORK_API_URL=https://lfexppnvvkqzygbwqnkv.supabase.co/functions/v1/cowork-api
   COWORK_API_KEY=<chuoi-bi-mat>
   ```
4. Tạo scheduled task (cron `0 8 * * *`) với prompt bên dưới.

## API
Mọi request có header `x-api-key: $COWORK_API_KEY`.

| Method | Đường dẫn | Việc |
|---|---|---|
| GET | `/keywords` | Keyword đã duyệt chưa có outline (`?all=1` lấy hết) |
| POST | `/outlines` | Đẩy outline, luôn ở trạng thái chưa duyệt |
| GET | `/outlines/approved` | Outline bạn đã bấm duyệt và chưa có bài |
| POST | `/articles` | Đẩy bài viết, luôn ở trạng thái chưa duyệt (chỉ nhận khi outline đã duyệt) |

Body `POST /outlines`: `{approved_keyword_id, keyword, outline_md, short_kws[], long_kws[], research{}}`
Body `POST /articles`: `{outline_id, title, content_md, meta_description, seo_score, word_count}`

## Prompt cho scheduled task
```
Làm việc trong thư mục tnc-seo-content, dùng skill tnc-seo-content. Đọc COWORK_API_URL và COWORK_API_KEY từ .env
(không in khóa ra màn hình). Mọi lời gọi API gửi header x-api-key.

PHẦN A, lập outline:
1. GET {COWORK_API_URL}/keywords. Với mỗi keyword (tối đa 5 keyword/lần chạy):
2. Làm Bước 2 và Bước 3 của skill tnc-seo-content (chạy serp_keyword.py, phân tích đối thủ, chọn 2-3 key phụ ngắn
   và 2-3 key phụ dài, lập outline gồm title, mở đầu, H2/H3, FAQ 5 câu, Kết luận).
3. POST {COWORK_API_URL}/outlines với approved_keyword_id=id, keyword, outline_md, short_kws, long_kws,
   research (PAA và danh sách đối thủ). DỪNG ở đây với keyword này, không viết bài.

PHẦN B, viết bài:
4. GET {COWORK_API_URL}/outlines/approved. Với mỗi outline (tối đa 5):
5. Viết bài theo Bước 4 của skill, dùng đúng 100% key phụ trong outline đã duyệt; chạy evaluate_seo.py
   và sửa đến khi điểm >= 90; tạo meta description 160-170 ký tự (Bước 5).
   Lưu bài vào seo_output/<slug>/<slug>.md (kèm <slug>.seo_score.json cùng thư mục) TRƯỚC khi đẩy lên API.
6. POST {COWORK_API_URL}/articles với outline_id, title, content_md, meta_description, seo_score, word_count.

Nếu một lời gọi trả 409 (đã có) thì bỏ qua mục đó. Cuối cùng báo cáo: số outline đã đẩy, số bài đã đẩy, lỗi nếu có.
Không bao giờ tự duyệt, không sửa trạng thái; việc duyệt do người dùng bấm trên dashboard.
```
