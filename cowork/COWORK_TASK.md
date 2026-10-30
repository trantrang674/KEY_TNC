# Cowork: tự động lập outline và viết bài từ keyword đã duyệt

Chạy 1 lần/ngày. Thư mục làm việc của task phải là `C:\Users\MK01\Documents\GEMNI ANTIGRAVITY\tnc-seo-content`
(nơi có skill `tnc-seo-content`, `seo-keyword-research`, `evaluate_seo.py` và `.env` chứa SerpApi key).

## Cài đặt một lần
1. Supabase SQL Editor (project TNC): chạy `database/seo_content.sql` , `database/cowork_notifications.sql` (bảng cho chuông thông báo), `database/seo_articles_google_doc.sql` (link Docs) và `database/cowork_heartbeat.sql` (nhịp hoạt động của Cowork).
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
| POST | `/notifications` | Báo tin lên chuông thông báo trên dashboard |

| POST | `/heartbeat` | Báo "Cowork vừa chạy": `{status: "running"\|"ok"\|"error", summary?}` (cần `database/cowork_heartbeat.sql`) |

`GET /keywords` trả thêm `rejected_note` (lý do người duyệt từ chối outline trước), `GET /outlines/approved` trả thêm `rejected_article_note` (lý do từ chối bài trước).

Body `POST /notifications`: `{level: "info"|"success"|"warning"|"error", title, message?, keyword?}`

Body `POST /outlines`: `{approved_keyword_id, keyword, outline_md, short_kws[], long_kws[], research{}}`
Body `POST /articles`: `{outline_id, title, content_md, meta_description, seo_score, word_count, google_doc_url?}`
(`google_doc_url` chỉ nhận link bắt đầu bằng docs.google.com hoặc drive.google.com; chạy `database/seo_articles_google_doc.sql` một lần để có cột này.)

## Prompt cho scheduled task
```
Làm việc trong thư mục tnc-seo-content, dùng skill tnc-seo-content. Đọc COWORK_API_URL và COWORK_API_KEY từ .env
(không in khóa ra màn hình). Mọi lời gọi API gửi header x-api-key.

BƯỚC 0 (đầu lần chạy): POST {COWORK_API_URL}/heartbeat với {"status":"running","summary":"Bắt đầu chạy"}.
Dashboard dựa vào đây để hiện "Cowork chạy lần cuối" và báo đỏ nếu quá 26 giờ không có nhịp. Lỗi gọi /heartbeat không được làm dừng lần chạy.

PHẦN A, lập outline:
1. GET {COWORK_API_URL}/keywords. Với mỗi keyword (tối đa 5 keyword/lần chạy):
   Nếu keyword có rejected_note (không rỗng) nghĩa là outline lần trước bị người duyệt TỪ CHỐI với lý do đó:
   đọc kỹ lý do và lập outline mới sửa đúng chỗ bị chê, không lặp lại lỗi cũ.
2. Làm Bước 2 và Bước 3 của skill tnc-seo-content (chạy serp_keyword.py, phân tích đối thủ, chọn 2-3 key phụ ngắn
   và 2-3 key phụ dài, lập outline gồm title, mở đầu, H2/H3, FAQ 5 câu, Kết luận).
3. POST {COWORK_API_URL}/outlines với approved_keyword_id=id, keyword, outline_md, short_kws, long_kws,
   research (PAA và danh sách đối thủ, KÈM research.report_md = toàn bộ nội dung file seo_output/<slug>/report.md
   để nút XEM REPORT trên dashboard hiển thị được). DỪNG ở đây với keyword này, không viết bài.
   BẮT BUỘC: research.report_md phải là nội dung THẬT của report.md (đọc file rồi đưa nguyên văn vào), không được để
   trống hay bỏ trường này, nếu không dashboard báo "Chưa có report cho keyword này". Trước khi POST, kiểm tra
   report_md không rỗng. Nếu lỡ thiếu thì chạy `python sync_reports.py --apply` (thư mục tnc-seo-keyword-news/KEY_TNC)
   để đồng bộ bù, rồi ghi rõ trong báo cáo cuối.
   outline_md viết theo đúng mẫu để dashboard trình bày như bản "Dàn ý đề xuất":
     # Outline: <từ khóa chính>
     **Title đề xuất (N ký tự):** <title>
     **Đoạn mở đầu:** <1 đoạn, từ khóa chính ở đầu câu đầu tiên>
     ## <H2>            (dòng dưới là mô tả ngắn nội dung H2)
     ### <H3>           (dòng dưới là mô tả ngắn nội dung H3)
     ## FAQ             (mỗi câu hỏi 1 dòng gạch đầu dòng "- ", đủ 5 câu)
     ## Kết luận        (kèm câu kết theo dõi Tin Tức TNC)
   Không đưa danh sách key phụ vào outline_md (đã có trong short_kws / long_kws).

PHẦN B, viết bài:
4. GET {COWORK_API_URL}/outlines/approved. Với mỗi outline (tối đa 5):
   Nếu outline có rejected_article_note (không rỗng) nghĩa là bài lần trước bị người duyệt TỪ CHỐI với lý do đó:
   đọc kỹ lý do và viết lại bài sửa đúng chỗ bị chê (vẫn giữ 100% key phụ và điểm SEO >= 90).
5. Viết bài theo Bước 4 của skill, dùng đúng 100% key phụ trong outline đã duyệt; chạy evaluate_seo.py
   và sửa đến khi điểm >= 90; tạo meta description 160-170 ký tự (Bước 5).
   Lưu bài vào seo_output/<slug>/<slug>.md (kèm <slug>.seo_score.json cùng thư mục) TRƯỚC khi đẩy lên API.
6. Tạo file Google Docs cho bài bằng connector Google Drive/Docs, trong thư mục Drive có ID
   1fRp_DIEG6NszTzxzJSet3BFqAXKRlUTz (https://drive.google.com/drive/folders/1fRp_DIEG6NszTzxzJSet3BFqAXKRlUTz).
   Tên file = title của bài; nội dung = content_md đã định dạng (H1/H2/H3, danh sách, bảng, in đậm, link giữ nguyên),
   thêm meta description ở đầu file. Lấy link file Docs (https://docs.google.com/document/d/<id>/edit).
   Nếu connector lỗi hoặc không có quyền vào thư mục: KHÔNG dừng, vẫn làm bước 7 với google_doc_url bỏ trống,
   và gửi thông báo level "warning" (title "Không tạo được Google Docs", message ghi lý do, keyword tương ứng).
7. POST {COWORK_API_URL}/articles với outline_id, title, content_md, meta_description, seo_score, word_count,
   google_doc_url (link Docs ở bước 6; dashboard sẽ hiện nút "Docs").

THÔNG BÁO LÊN CHUÔNG DASHBOARD (POST {COWORK_API_URL}/notifications, body {level, title, message, keyword}):
- Mỗi keyword lỗi (serp_keyword.py hỏng, không đủ PAA, evaluate_seo.py không đạt 90 sau nhiều lần sửa, API trả lỗi khác 409):
  level "error" hoặc "warning", title ngắn nêu việc, message ghi nguyên nhân, keyword là từ khóa liên quan.
- Cuối lần chạy: 1 thông báo level "success" nếu mọi thứ ổn, nội dung "Đã đẩy N outline, M bài chờ duyệt"; nếu có lỗi thì level "warning"
  kèm số mục lỗi. Nếu không có keyword nào để xử lý thì level "info" "Không có keyword mới".
- Thông báo chỉ là tin cho người xem, không chứa khóa API hay dữ liệu nhạy cảm. Lỗi gọi /notifications không được làm dừng cả lần chạy.

KẾT THÚC LẦN CHẠY: POST {COWORK_API_URL}/heartbeat với {"status":"ok","summary":"Đã đẩy N outline, M bài"} nếu chạy xong bình thường
(kể cả khi không có keyword nào để xử lý); {"status":"error","summary":"<lý do ngắn>"} nếu cả lần chạy hỏng nặng, không làm được gì.

Nếu một lời gọi trả 409 (đã có) thì bỏ qua mục đó. Cuối cùng báo cáo: số outline đã đẩy, số bài đã đẩy, lỗi nếu có.
Không bao giờ tự duyệt, không sửa trạng thái; việc duyệt do người dùng bấm trên dashboard.
```
