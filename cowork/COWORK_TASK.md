# Cowork: tự động lập outline và viết bài từ keyword đã duyệt

Chạy 1 lần/ngày. Thư mục làm việc của task phải là `C:\Users\MK01\Documents\GEMNI ANTIGRAVITY\tnc-seo-content`
(nơi có `CLAUDE.md`, `.agents/skills/tnc-viet-bai-tin`, `.agents/skills/tnc-viet-bai-review`, `seo-keyword-research`, `evaluate_seo.py`, `cham-diem-seo.md` và `.env` chứa SerpApi key).
Cowork chạy cục bộ và chỉ dùng quy chuẩn trong thư mục đó, không dùng skill nào có sẵn của app.

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
4. Tạo scheduled task (cron `0 10 * * *`) với prompt bên dưới.

## API
Mọi request có header `x-api-key: $COWORK_API_KEY`.

| Method | Đường dẫn | Việc |
|---|---|---|
| GET | `/keywords` | Keyword đã duyệt chưa có outline (`?all=1` lấy hết) |
| POST | `/outlines` | Đẩy outline, luôn ở trạng thái chưa duyệt |
| GET | `/outlines/approved` | Outline bạn đã bấm duyệt và chưa có bài |
| POST | `/articles` | Đẩy bài viết, luôn ở trạng thái chưa duyệt (chỉ nhận khi outline đã duyệt) |
| POST | `/notifications` | Báo tin lên chuông thông báo trên dashboard |

| POST | `/heartbeat` | Báo "Cowork vừa chạy": `{status: "running"|"ok"|"error", summary?}` (cần `database/cowork_heartbeat.sql`) |

`GET /keywords` trả thêm `rejected_note` (lý do người duyệt từ chối outline trước), `GET /outlines/approved` trả thêm `rejected_article_note` (lý do từ chối bài trước).

**Loại nội dung (cần chạy `database/content_type.sql` một lần):** `GET /keywords` và `GET /outlines/approved` nhận `?type=news|review`; mỗi mục trả `content_type` và `review_input` (dữ liệu thật người nhập cho bài đánh giá: `product_name, tnc_url, specs, pros, cons, tester_notes, has_hands_on, image_folder`; có thể null).
Loại bài do NGƯỜI chọn trên dashboard (ô "Loại bài" ở form Thêm KEYWORD; keyword từ Top 20 luôn là `news`). `POST /outlines` và `POST /articles` tự lấy `content_type` từ keyword/outline, không nhận từ body.
`POST /articles` trả 400 nếu `word_count` không phải số nguyên >= 1.

Body `POST /notifications`: `{level: "info"|"success"|"warning"|"error", title, message?, keyword?}`

Body `POST /outlines`: `{approved_keyword_id, keyword, outline_md, short_kws[], long_kws[], research{}}`
Body `POST /articles`: `{outline_id, title, content_md, meta_description, seo_score, word_count, google_doc_url?}`
(`google_doc_url` chỉ nhận link bắt đầu bằng docs.google.com hoặc drive.google.com; chạy `database/seo_articles_google_doc.sql` một lần để có cột này.)

## Prompt cho scheduled task
```
Làm việc trong thư mục C:\Users\MK01\Documents\GEMNI ANTIGRAVITY\tnc-seo-content. Đọc CLAUDE.md ở gốc thư mục, rồi chỉ làm theo
.agents/skills/tnc-viet-bai-tin/SKILL.md (content_type = "news") hoặc .agents/skills/tnc-viet-bai-review/SKILL.md (content_type = "review").
LOẠI BÀI DO NGƯỜI CHỌN trên dashboard, nằm ở trường content_type của từng keyword/outline: KHÔNG tự đoán loại từ nội dung keyword. KHÔNG dùng skill nào có sẵn của app (đặc biệt skill tnc-seo-content của app). Cấm mọi link trong bài.
Đọc COWORK_API_URL và COWORK_API_KEY từ .env
(không in khóa ra màn hình). Mọi lời gọi API gửi header x-api-key.

BƯỚC 0 (đầu lần chạy): POST {COWORK_API_URL}/heartbeat với {"status":"running","summary":"Bắt đầu chạy"}.
Dashboard dựa vào đây để hiện "Cowork chạy lần cuối" và báo đỏ nếu quá 26 giờ không có nhịp. Lỗi gọi /heartbeat không được làm dừng lần chạy.

QUY TẮC RIÊNG CHO BÀI ĐÁNH GIÁ (content_type = "review"), áp dụng cả Phần A và Phần B:
- Mỗi keyword/outline review có trường review_input (có thể null hoặc thiếu một số ô): {product_name?, tnc_url?, specs?, pros?, cons?, tester_notes?, has_hands_on?, image_folder?}
  do NGƯỜI nhập trên dashboard. Đây là nguồn dữ liệu thật duy nhất cho thông số và trải nghiệm.
- Thông số: chỉ lấy từ review_input.specs, từ trang sản phẩm tnc_url (chỉ để ĐỌC, cấm chèn link vào bài) và thông số do hãng công bố có trong report.md. Thiếu thông số nào thì bỏ qua
  hoặc ghi "theo thông số công bố", TUYỆT ĐỐI KHÔNG bịa số liệu, KHÔNG bịa điểm benchmark, thời lượng pin hay nhiệt độ.
- Trải nghiệm dùng thật: chỉ được viết khi review_input.has_hands_on = true, và chỉ dựa trên pros, cons, tester_notes. Nếu has_hands_on không phải true thì CẤM mọi câu kiểu
  "chúng tôi đã dùng thử", "qua trải nghiệm thực tế", "khi sử dụng thấy", "test thực tế"; viết theo hướng tổng hợp thông số công bố và phù hợp với ai.
- Folder ảnh: image_folder nếu có, nếu trống dùng tên sản phẩm trong "hình ảnh review sản phẩm/".
- Nếu thiếu dữ liệu quan trọng (không có specs và không có tnc_url) thì vẫn lập outline từ thông số công bố, nhưng gửi thông báo level "warning" (keyword tương ứng)
  nhắc người dùng nhập dữ liệu trên dashboard.

PHẦN A, lập outline:
1. Chạy 2 lượt, mỗi lượt đúng 1 skill: GET {COWORK_API_URL}/keywords?type=news (skill tnc-viet-bai-tin) rồi GET {COWORK_API_URL}/keywords?type=review
   (skill tnc-viet-bai-review). Tổng tối đa 5 keyword/lần chạy. Với mỗi keyword:
   Nếu keyword có rejected_note (không rỗng) nghĩa là người duyệt đã YÊU CẦU CHỈNH SỬA outline lần trước (nhận xét thêm/bớt/đổi gì đó):
   đọc kỹ nhận xét và lập outline mới làm đúng từng ý được yêu cầu, không lặp lại phần bị góp ý.
2. Làm Bước 2 và Bước 3 của skill (chạy serp_keyword.py, phân tích đối thủ, chọn đúng 4-6 key phụ gồm 2-3 key ngắn
   và 2-3 key dài, lập outline gồm title dưới ~60 ký tự, mở đầu, H2/H3, FAQ 5 câu, Kết luận).
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
     ## Kết luận        (kèm câu kết theo dõi Tin Tức TNC với bài tin, hoặc CTA Hotline 1900 6078 / Showroom Thành Nhân TNC với bài review)
   Không đưa danh sách key phụ vào outline_md (đã có trong short_kws / long_kws).

PHẦN B, viết bài:
4. GET {COWORK_API_URL}/outlines/approved?type=news (skill tin) rồi GET {COWORK_API_URL}/outlines/approved?type=review (skill review). Với mỗi outline (tổng tối đa 5):
   Nếu outline có rejected_article_note (không rỗng) nghĩa là người duyệt đã YÊU CẦU CHỈNH SỬA bài lần trước:
   đọc kỹ nhận xét và viết lại bài làm đúng từng ý được yêu cầu (vẫn giữ 100% key phụ và điểm SEO >= 90).
5. Viết bài theo Bước 4 của skill, dùng đúng 100% key phụ trong outline đã duyệt; tuân thủ nghiêm ngặt 13 tiêu chí trong cham-diem-seo.md:
   - Bài dài 1,500-2,200 từ, mỗi key phụ lặp 2-5 lần, tuân thủ mục 3.7 và 6.7 (không lộ văn phong AI), cấm mọi link và không dùng em-dash "—".
   - Bắt buộc chèn khối "## Meta description" ở cuối cùng của file bài viết (150-160 ký tự, từ khóa chính ở ngay đầu câu).
   - Hình ảnh (Tiêu chí 9): tỉ lệ 3:2, 900x600 px, .jpg/.jpeg, caption không chứa từ khóa chính; bài tin >= 2 hình, bài review >= 5 hình (mỗi H2 chèn 1 ảnh, kiểm tra folder "hình ảnh review sản phẩm/<tên_sản_phẩm>/" để lấy ảnh thật hoặc chèn ảnh minh họa đúng quy chuẩn).
   - Chạy evaluate_seo.py và sửa đến khi điểm >= 90 (thang 100):
       Bài tin tức: python evaluate_seo.py --file "seo_output/<slug>/<slug>.md" --keyword "<keyword>" --short-kws "<short_kws của outline đã duyệt, cách nhau bởi dấu phẩy>" --long-kws "<long_kws của outline đã duyệt>" --quiet
       Bài review:  python evaluate_seo.py --file "seo_output/<slug>/<slug>.md" --keyword "<keyword>" --short-kws "<short_kws của outline đã duyệt, cách nhau bởi dấu phẩy>" --long-kws "<long_kws của outline đã duyệt>" --type review --quiet
   - TUYỆT ĐỐI KHÔNG dùng --auto-kws (cờ này lấy key rác từ SerpApi, không phải key phụ đã duyệt). Chỉ dùng --short-kws/--long-kws lấy từ outline đã duyệt.
   - Kết quả chỉ ĐẠT khi dòng đầu in [PASS] và KHÔNG có dòng "CHẶN" (mật độ từ khóa chính 0.8%-1.2%, key phụ 4-6 từ mỗi từ lặp 2-5 lần). Có "CHẶN" thì sửa bài rồi chấm lại, dù tổng >= 90.
   - word_count = trường "word_count" trong <slug>.seo_score.json (hoặc số sau "word_count=" ở dòng kết quả). KHÔNG được gửi 0 hay bỏ trống; seo_score cũng lấy từ file này. Phải gửi đúng số của lần chấm cuối cùng.
   - Nếu dòng kết quả có "CẢNH BÁO ảnh chưa có file": ghi rõ trong thông báo level "warning" (keyword tương ứng) rằng ảnh chưa được chèn thật, không được báo hoàn tất như đã có ảnh.
   - Lưu bài vào seo_output/<slug>/<slug>.md (kèm <slug>.seo_score.json cùng thư mục) TRƯỚC khi đẩy lên API.
6. Tạo file Google Docs cho bài bằng connector Google Drive/Docs, trong thư mục Drive có ID
   1fRp_DIEG6NszTzxzJSet3BFqAXKRlUTz (https://drive.google.com/drive/folders/1fRp_DIEG6NszTzxzJSet3BFqAXKRlUTz).
   Tên file = title của bài; nội dung = content_md đã định dạng (H1/H2/H3, danh sách, bảng, in đậm, không chèn link),
   thêm meta description ở đầu file. Lấy link file Docs (https://docs.google.com/document/d/<id>/edit).
   Nếu connector lỗi hoặc không có quyền vào thư mục: KHÔNG dừng, vẫn làm bước 7 với google_doc_url bỏ trống,
   và gửi thông báo level "warning" (title "Không tạo được Google Docs", message ghi lý do, keyword tương ứng).
7. TRƯỚC khi POST, kiểm tra word_count >= 1500 và seo_score >= 90 từ file .seo_score.json; sau khi POST, GET lại hoặc đọc phản hồi để chắc word_count không phải 0. POST {COWORK_API_URL}/articles với outline_id, title, content_md, meta_description, seo_score, word_count,
   google_doc_url (link Docs ở bước 6; dashboard sẽ hiện nút "Docs").

PHẦN C, quét & chấm điểm lại bài cũ NÊN LÀM MỚI (HOÀN TOÀN KHÔNG TỐN LƯỢT SERPAPI, chỉ ĐỀ XUẤT):
8. Chạy script chẩn đoán tự động: `python refresh_audit.py --limit 3 --json`
   (Script tự gọi /refresh-candidates, bỏ qua URL đã báo trong 7 ngày theo seo_output/refresh_log.json,
   quét lại file bài viết cục bộ bằng evaluate_seo.py, rà soát mốc năm cũ, gap nội dung và tạo thư mục seo_output/<slug>/seo_audit/
   chứa refresh_report.md cùng file chấm điểm lại để không lẫn với file report gốc).
   Lỗi gọi script (404 nếu chưa deploy Edge Function) không được làm dừng lần chạy: bỏ qua cả Phần C.
9. TUYỆT ĐỐI KHÔNG GỌI serp_keyword.py hay SerpApi (0 tốn lượt SerpApi).
   Với mỗi bài được script trả về, lấy trường `notification` và POST lên {COWORK_API_URL}/notifications
   (level "info", title "Nên làm mới: <title rút gọn>", message gồm lý do GSC, điểm chấm lại mới vs cũ,
   và 2-3 đề xuất sửa On-page, keyword = keyword của bài).
   KHÔNG POST /outlines hay /articles cho việc này, KHÔNG sửa bài đã đăng; người dùng tự quyết định trên Dashboard.

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
