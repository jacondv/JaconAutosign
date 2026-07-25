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
