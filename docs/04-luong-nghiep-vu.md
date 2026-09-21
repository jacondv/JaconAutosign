# Luồng nghiệp vụ chi tiết

## Luồng A — Tạo Template (thực hiện 1 lần cho mỗi loại tài liệu)

```
1. Người dùng chọn "Tạo template mới"
2. Chọn 1 file PDF mẫu đại diện (VD: 1 hợp đồng mẫu đã có đủ số trang thường gặp)
3. Ứng dụng render các trang PDF thành ảnh, hiển thị dạng cuộn dọc / chọn trang
4. Người dùng chọn trang cần đặt chữ ký (VD: trang 1, hoặc trang cuối)
5. Người dùng dùng chuột vẽ 1 hình chữ nhật tại vị trí cần ký trên trang đó
   - Có thể kéo/resize lại khung cho chính xác
   - Có thể phóng to (zoom) trang để vẽ chính xác hơn
6. (Nếu có nhiều vị trí ký trong cùng tài liệu) Lặp lại bước 4-5 cho trang khác
7. Với mỗi khung vẽ, chọn kiểu tham chiếu trang:
   - "Trang số cụ thể" (VD trang 1)
   - "Trang đầu tiên" / "Trang cuối cùng" (để áp dụng đúng khi các file khác số trang)
8. Đặt tên cho template (VD: "Hợp đồng lao động - chữ ký giám đốc")
9. Lưu template → ghi ra file JSON trong thư mục templates/
```

## Luồng B — Ký hàng loạt (chạy thường xuyên, mục tiêu chính cần tối ưu tốc độ)

```
1. Người dùng mở màn hình "Ký hàng loạt"
2. Chọn Template đã lưu từ danh sách (hoặc tìm kiếm theo tên)
3. Chọn danh sách file cần ký:
   - Chọn nhiều file rời rạc, hoặc
   - Chọn cả thư mục (quét toàn bộ .pdf, có tuỳ chọn gồm thư mục con)
4. Ứng dụng hiển thị danh sách file kèm số trang, và ĐÁNH DẤU CẢNH BÁO
   những file có số trang không đủ so với yêu cầu template (VD template
   cần "trang 3" nhưng file chỉ có 2 trang)
5. (Tuỳ chọn) Người dùng bấm "Xem trước" 1 file bất kỳ trong danh sách để
   xác nhận khung ký hiển thị đúng vị trí mong muốn
6. Người dùng chọn file chứng thư số .p12 (hoặc dùng file đã chọn lần trước)
7. Chọn thư mục output (mặc định: thư mục con "signed" cạnh file gốc)
8. Bấm "Bắt đầu ký" → hộp thoại yêu cầu nhập mật khẩu chứng thư số
9. Nhập mật khẩu 1 LẦN DUY NHẤT → ứng dụng xác thực mật khẩu ngay
   (mở thử .p12) → báo lỗi ngay nếu sai, không chạy batch nếu mật khẩu sai
10. Ứng dụng chạy tuần tự/song song qua từng file:
    a. Đọc file PDF, resolve trang thật theo template (first/last/số cụ thể)
    b. Nếu thiếu trang → đánh dấu lỗi, bỏ qua file, tiếp tục file kế
    c. Chèn appearance chữ ký tại đúng toạ độ, ký PAdES bằng .p12 + mật khẩu
    d. Ghi file kết quả ra thư mục output
    e. Cập nhật tiến trình UI (X/N, thanh progress, trạng thái từng dòng)
11. Kết thúc batch → hiển thị bảng tổng kết: N file thành công, M file lỗi
    (kèm lý do), cho phép xuất báo cáo CSV/log
12. Người dùng có thể bấm mở nhanh 1 file đã ký để kiểm tra bằng mắt
```

## Luồng C — Xử lý lỗi giữa chừng

```
- Lỗi 1 file (thiếu trang / PDF hỏng / PDF có mật khẩu mở file) →
  ghi nhận lỗi, KHÔNG dừng batch, tiếp tục file tiếp theo
- Người dùng bấm "Huỷ" giữa batch → dừng sau khi file hiện tại xử lý xong
  (không huỷ giữa chừng 1 file đang ghi, tránh file output bị hỏng dở)
- Nếu ứng dụng crash/tắt đột ngột → khi mở lại, các file đã ký thành công
  trước đó vẫn nguyên vẹn trong thư mục output; người dùng chạy lại batch
  với danh sách file còn lại (có thể cần tính năng "bỏ qua file đã có
  trong thư mục output" ở giai đoạn sau — xem câu hỏi mở)
```

## Luồng D — Tự động chuyển file đã ký vào folder dự án (đã cài đặt)

> Code: `src/autosign/services/project_folder_service.py` (quy tắc khớp
> folder + hàm move) và `src/autosign/ui/sign_screen.py` (nơi gọi vào,
> phương thức `_auto_move_if_matched`, `_manual_move_current_file`,
> `_perform_move`, `_is_fully_signed`).

### Bối cảnh
File PDF cần ký thường nằm chung thư mục (inbox) với các folder dự án đã
đánh số, ví dụ:

```
Downloads\2\
    1304-XYZ.pdf
    1304-Electrical\      (folder dự án)
    12. Chassic\          (folder dự án khác)
```

Sau khi ký xong, thay vì để file nằm trong `Signed_<tên>\` (hoặc folder
output tuỳ chỉnh), ứng dụng tự động "file" nó vào đúng folder dự án tương
ứng và dọn file gốc chưa ký đi.

### 1. Khi nào tự động chạy (không cần xác nhận)
Sau **mỗi lần ký xong 1 file** (`SignScreen._on_progress`), ứng dụng kiểm
tra `_is_fully_signed(output_path)`: so `get_signed_pages(output_path)`
với tổng số trang của file. Chỉ khi **toàn bộ trang đã có chữ ký** (bất kể
lần ký này dùng scope "Current/First/Last/All page" — có thể là kết quả
cộng dồn của nhiều lần ký từng trang) thì mới coi là "xong" và kích hoạt
auto-move. Ký dở (chưa đủ trang) thì bỏ qua, để dành cho nút Move thủ công.

### 2. Quy tắc khớp folder (`find_matching_project_folder`)
Thử lần lượt 2 quy tắc, dùng quy tắc nào tìm được kết quả trước:

**Quy tắc 1 — mã số đầu tên file** (`_match_by_leading_digits`):
1. Lấy **số ở đầu tên file** (regex `^(\d+)`), ví dụ `1304-XYZ.pdf` → `"1304"`.
2. Duyệt các folder con **cùng cấp với file gốc** (cùng thư mục cha), lấy
   số ở đầu tên mỗi folder, ví dụ `1304-Electrical` → `"1304"` (4 chữ số),
   `12. Chassic` → `"12"` (2 chữ số).
3. Độ dài số của **folder** quyết định so khớp bao nhiêu chữ số đầu của
   tên file: folder 2 số → so 2 số đầu file; folder 4 số → so 4 số đầu file.
4. Chỉ nhận kết quả khi có **đúng 1 folder khớp**. Nếu không folder nào
   khớp, hoặc khớp nhiều hơn 1 (kể cả khớp ở độ dài số khác nhau, ví dụ
   file vừa khớp folder 2 số vừa khớp folder 4 số) → coi là mơ hồ, quy tắc
   này trả về `None` (thử tiếp quy tắc 2).
5. **Dò thêm 1 cấp con** (`_descend_one_level`, tối đa 2 cấp): nếu folder
   vừa khớp ở bước trên (VD `1304-Electrical`) bên trong lại có folder
   con, áp dụng lại đúng quy tắc 1 (so số đầu) giữa các folder con đó với
   tên file. Có khớp đúng 1 folder con → move vào folder con đó (VD
   `1304-Electrical/130402-Wiring/`); không khớp, khớp nhiều hơn 1, hoặc
   không có folder con nào → giữ nguyên folder cấp 1 đã tìm được. Không dò
   xuống cấp thứ 3.

**Quy tắc 2 — tên folder xuất hiện trong tên file** (`_match_by_name_substring`),
áp dụng cho các file không bắt đầu bằng số (không khớp quy tắc 1):
1. Duyệt các folder con cùng cấp, giữ lại folder nào có **tên folder xuất
   hiện như 1 cụm con trong tên file** (so sánh không phân biệt hoa/thường).
   Ví dụ `JSA-T43US-A.pdf` chứa cụm `T43US` → khớp folder `T43US`.
2. Nếu có nhiều folder cùng khớp, chọn folder có **tên dài nhất** (khớp cụ
   thể hơn). Ví dụ `JSV6-EMU-ABCD.pdf` khớp cả folder `JSV6` và
   `JSV6-EMU` → chọn `JSV6-EMU` vì tên dài hơn.
3. Nếu không folder nào khớp, hoặc nhiều folder cùng khớp và cùng tên dài
   nhất (không phân biệt được) → mơ hồ, trả về `None` → không tự động.

### 3. Thực hiện move (`move_signed_file`)
- Move file đã ký (từ `Signed_<tên>\...`) vào folder dự án đã khớp, giữ
  nguyên tên file.
- Xoá file PDF gốc (chưa ký) ở thư mục inbox — vì đã "chuyển chỗ" xong.
- Nếu trong folder đích đã có sẵn file trùng tên → không tự ghi đè, ném
  `MoveCollisionError`; UI hỏi người dùng Overwrite hay bỏ qua.
- Trước khi move, gọi `PdfViewerWidget.release_file_handles()` để đóng
  handle pdfium mà khung xem (hover/chọn text) có thể đang giữ mở trên
  chính file đó — tránh lỗi Windows "file đang được sử dụng" (WinError 32).

### 4. Thông báo
- Auto-move (im lặng phần lớn): chỉ hiện dòng trạng thái ngắn dạng
  `Moved <tên file> → <tên folder>\` ở khu vực tóm tắt (`SignControlPanel.set_summary`),
  không có hộp thoại xác nhận — **trừ khi trùng tên** thì mới hỏi.
- Move thủ công: xác nhận xong hiện hộp thoại thông báo đã move.

### 5. Nút "Move" thủ công
Nằm cạnh Remove/Reset/Clear trong danh sách file, tác động lên **file
đang mở** (không phải file đang chọn nhiều), dùng cho các file ký dở dang
(không rơi vào auto-move ở mục 1):
1. Kiểm tra file đã có output đã ký chưa — chưa có thì báo và dừng.
2. Áp dụng quy tắc khớp folder ở mục 2.
3. Không tìm được folder khớp → mở hộp thoại chọn thư mục đích thủ công.
4. Move theo đúng cơ chế ở mục 3 (kể cả xử lý trùng tên).

## Luồng E — Kiểm tra khung tên bản vẽ (title block, đã cài đặt)

> Code: `src/autosign/services/title_block_service.py` (trích xuất +
> kiểm tra), `src/autosign/models/template.py` (`TitleBlockField`,
> `TitleBlockFieldType`), `src/autosign/ui/template_designer.py` +
> `src/autosign/ui/title_block_field_dialog.py` (vẽ khung ở Template
> Designer), `src/autosign/ui/sign_screen.py`
> (`_compute_title_block_warnings`, `_sync_preview_overlay`).

### Bối cảnh
Bản vẽ kỹ thuật có khung tên (title block) chứa `Drawing No.`, khối
`DRAWN/CHK'D/APP'D` (tên tắt + ngày), và 1 bảng lịch sử revision (REV,
DESCRIPTION, BY, CKD, APP, DATE). **Dòng dưới cùng luôn là REV 0** (bản
đầu tiên) và **không bao giờ đổi vị trí**; mỗi khi có revision mới, dòng
mới được chèn liền phía trên dòng mới nhất hiện tại, đẩy khối dòng dần
lên cao hơn. Tính năng này đọc các giá trị trong khung tên ra và đối
chiếu chéo để phát hiện sai sót trước khi ký - **chỉ cảnh báo, không
chặn ký**.

### 1. Khai báo khung ở Template Designer
- Thêm hẳn 1 "Draw mode" bên cạnh khung chữ ký: **Signature box** (như
  cũ) hoặc **Title block field** (mới). Ở mode field, vẽ xong sẽ hiện
  hộp thoại chọn loại field (`TitleBlockFieldDialog`): `Drawing No.`,
  `DRAWN/CHK'D/APP'D - name/date`, hoặc `Revision table - newest ...`
  (REV No./BY/CKD/APP/DATE), và trang chứa khung tên (trang này/đầu/cuối).
- Với field loại "Revision table": vẽ khung **sát đúng dòng REV 0** (dòng
  dưới cùng, vị trí cố định, không đổi) - không cần nhập thêm gì khác.
  Chiều cao khung tự động dùng làm khoảng cách giữa các dòng; app quét
  lên trên cho tới khi gặp dòng trống để tự tìm dòng mới nhất, nên vẽ
  càng sát khung thực tế thì càng chính xác.
- Danh sách "Title block fields" hiển thị cạnh danh sách Signature
  boxes, có Edit/Delete riêng. Hoàn toàn tùy chọn - template không khai
  báo field nào thì tính năng tự tắt cho template đó.

### 2. Trích xuất (`extract_title_block_info`, `_extract_newest_revision_row`)
- Field cố định (Drawing No., DRAWN/CHK'D/APP'D): đọc thẳng text trong
  đúng 1 khung đã vẽ.
- Field thuộc bảng revision: bắt đầu từ khung đã vẽ (dòng REV 0, index
  0), quét **lên trên** theo từng bước bằng đúng chiều cao khung, cho
  tới khi gặp 1 dòng **hoàn toàn trống** (không field nào có chữ) thì
  dừng - dòng trống đó là ranh giới trên của bảng đang dùng. Trong các
  dòng đã quét được (không trống), xác định dòng "mới nhất":
  1. Nếu có khai báo field `REV No.`: chọn dòng có **số REV lớn nhất**
     parse được (đáng tin cậy nhất, không phụ thuộc vị trí vật lý).
  2. Nếu không khai báo `REV No.`: dùng dòng **không trống cuối cùng**
     quét được (tức dòng trên cùng của khối đang dùng).
- Dùng `pypdfium2`'s `get_text_bounded()` đọc text thật trong toạ độ
  mỗi khung - **yêu cầu PDF có lớp text thật** (xuất từ CAD/Office),
  không hỗ trợ file scan/ảnh (không OCR).
- **Xử lý trang bị xoay (`/Rotate`)**: nhiều bản vẽ landscape được lưu
  dưới dạng trang PDF xoay 90°/270° (`page.get_rotation()` khác 0).
  Khung field luôn được vẽ/lưu theo hệ toạ độ **đã xoay** (giống hệt
  những gì hiển thị trên preview và Template Designer), nhưng
  `get_text_bounded()` của pdfium làm việc trên hệ toạ độ **gốc chưa
  xoay** của trang - 2 hệ này lệch nhau khi trang có rotation. Trước khi
  gọi `get_text_bounded()`, `_visual_rect_to_raw()` chuyển khung từ hệ
  đã xoay về hệ gốc (công thức riêng cho từng góc 90/180/270). Thiếu
  bước này thì mọi khung trên 1 trang bị xoay đều trích ra rỗng - từng
  là bug khiến 1 file bị lỗi thật (CHK'D/APP'D sai) nhưng không hiện
  cảnh báo nào, đã fix và test lại bằng đúng file đó.
- Nếu trang thực tế khác kích thước với lúc vẽ khung (`page_size_at_design_time`),
  khung được scale lại tương tự cách `SignatureBox` làm khi ký.
- Trả về `None` nếu template không có `title_block_fields` nào (bỏ qua
  hoàn toàn, không tốn chi phí xử lý).

### 3. Đối chiếu (`validate_title_block`) - toàn bộ chỉ sinh cảnh báo
1. **Drawing No. khớp tên file**: số/ký hiệu trích được chỉ cần là 1
   cụm con xuất hiện trong tên file (`stem`), VD `13080059` khớp với
   file `13080059-Rev0.pdf`.
2. **REV (ô riêng cạnh Drawing No. trong khung tên) = REV mới nhất
   trong bảng revision**: field `TITLE_REV_NUMBER` (ô "REV" nhỏ, độc
   lập với bảng revision - xem ảnh mẫu) phải khớp với `REV_NUMBER` (số
   REV của dòng mới nhất do bảng revision quét ra) - lệch nhau → cảnh
   báo.
3. **CHK'D (khung tên) = CKD (dòng revision mới nhất)**: lệch nhau →
   cảnh báo, đánh dấu cả 2 field.
4. **APP'D (khung tên) = APP (dòng revision mới nhất)**: tương tự.
5. **DRAWN (khung tên) = BY (dòng revision mới nhất)**: tương tự.
6. **Giá trị cố định theo Settings** (tùy chọn - `expected_ckd` /
   `expected_app` trong `AppSettings`, cấu hình ở Settings → "Title
   block check"): nếu đã điền, CHK'D/APP'D phải đúng bằng giá trị đó
   (VD CKD phải luôn là "DV"). Bỏ trống ở Settings thì bỏ qua rule này.
7. **Ngày không được ở tương lai so với ngày ký**: mọi field ngày
   (`DRAWN_DATE`, `CHKD_DATE`, `APPD_DATE`, `REV_DATE`) trích được, nếu
   parse được và muộn hơn ngày ký thực tế → cảnh báo.
8. **Thứ tự ngày: DRAWN ≤ CHK'D ≤ APP'D** (`_check_date_order`) - kiểm
   tra từng cặp độc lập (Drawn/Chkd, Chkd/Appd, Drawn/Appd), không bắt
   buộc phải có đủ cả 3 ngày mới kiểm tra được - thiếu 1 ngày ở giữa thì
   vẫn so được cặp còn lại.

### 4. Hiển thị cảnh báo
- **Thời điểm tính lại**: chỉ khi đang **xem trước 1 file cụ thể** - lúc
  chọn file trong danh sách (`_load_preview`) hoặc đổi Template trong
  khi file đó đang mở (`_on_template_changed`). Không chạy nền cho toàn
  bộ danh sách, không chạy lại lúc bấm Ký - đây thuần là công cụ xem
  trước, không phải một bước trong luồng ký. Kết quả cache theo file
  (`_title_block_info`, `_title_block_warnings`) nên đổi Settings
  (Expected CKD/APP) trong khi file đang mở sẵn thì cần chọn lại file
  (hoặc đổi qua đổi lại template) để tính lại.
- **Trên preview PDF** (`PageCanvas` - tham số `warning_ids`/`ok_ids`
  của `set_boxes`), theo kiểu đèn giao thông:
  - **Viền đỏ đậm**: field bị 1 rule cảnh báo (VD CHK'D lệch CKD).
  - **Viền xanh lá đậm**: field trích được giá trị và không bị cảnh báo
    nào - "đã kiểm tra, ổn".
  - **Viền xanh dương** (mặc định, như khung chữ ký): field không trích
    được gì (rỗng) - chưa xác minh được, không phải đỏ hay xanh lá.
  - Không hiện tên field kỹ thuật (VD `rev_ckd`) đè lên preview - chỉ
    màu viền nói lên trạng thái. Tên field vẫn hiện trong Template
    Designer để người thiết kế phân biệt được các khung.
- **Trong danh sách file**: file có cảnh báo hiện thêm `⚠ N` sau tên,
  chữ màu đỏ, tooltip liệt kê đầy đủ nội dung từng cảnh báo.
- Không có hộp thoại chặn ký nào - người dùng tự quyết định có ký tiếp
  hay sửa lại bản vẽ trước.

## Mô tả màn hình (wireframe dạng mô tả, chưa phải thiết kế UI cuối cùng)

### Màn hình 1 — Trang chủ
- 2 nút lớn: "Tạo/Sửa Template" và "Ký hàng loạt"
- Danh sách các lần chạy gần đây (tuỳ chọn, giai đoạn sau)

### Màn hình 2 — Template Designer
- Panel trái: xem trước trang PDF (có thanh chuyển trang, nút zoom)
- Trên panel: người dùng vẽ khung chữ nhật bằng kéo chuột
- Panel phải: danh sách các khung đã tạo (trang nào, toạ độ) — có thể click để highlight lại trên panel trái, sửa/xoá
- Nút "Lưu template", ô nhập tên template

### Màn hình 3 — Batch Runner
- Khu vực chọn Template (dropdown/list có tìm kiếm)
- Khu vực chọn file: nút "Thêm file", "Thêm thư mục", bảng danh sách file (tên, số trang, trạng thái/cảnh báo, nút xoá khỏi danh sách)
- Khu vực chọn chứng thư số (.p12) + đường dẫn output
- Nút "Bắt đầu ký" (to, nổi bật)
- Khi chạy: thanh tiến trình tổng + bảng trạng thái từng file cập nhật real-time

### Màn hình 4 — Báo cáo kết quả
- Tổng kết số liệu (thành công/thất bại)
- Bảng chi tiết từng file, cột "Mở file" để kiểm tra nhanh
- Nút "Xuất báo cáo CSV"
