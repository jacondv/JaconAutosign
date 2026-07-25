# Tổng quan dự án: Phần mềm ký số PDF hàng loạt (Batch PDF Digital Signer)

## 1. Bối cảnh & vấn đề hiện tại

Hiện tại việc ký số file PDF được thực hiện thủ công theo quy trình:

1. Mở từng file PDF trong phần mềm ký (VD: Adobe Acrobat, hoặc phần mềm của nhà cung cấp CA).
2. Với mỗi trang cần ký, dùng chuột vẽ một hình chữ nhật tại vị trí cần đặt chữ ký.
3. Nhập mật khẩu chứng thư số (.p12/.pfx) để xác nhận và chèn chữ ký vào đúng vị trí đó.
4. Lặp lại cho tất cả các trang trong file, rồi lặp lại cho tất cả các file cần ký.

Với tài liệu nhiều trang, nhiều file, thao tác vẽ khung + nhập mật khẩu lặp lại nhiều lần rất tốn thời gian.

## 2. Mục tiêu

Xây dựng một phần mềm **ký số PDF hàng loạt (batch)**:

- Cho một **mẫu (template)** xác định trước: vị trí (tọa độ) và kích thước khung chữ ký trên trang, áp dụng cho một hoặc nhiều trang trong file.
- Người dùng chỉ cần **cấu hình vị trí ký một lần** (bằng công cụ vẽ khung trực quan, giữ nguyên trải nghiệm "vẽ hình chữ nhật" hiện tại nhưng chỉ làm 1 lần cho mỗi loại tài liệu/mẫu).
- Sau đó chọn **nhiều file PDF cùng mẫu**, nhập mật khẩu chứng thư số **một lần**, phần mềm tự động ký toàn bộ các file/trang theo cấu hình đã lưu.
- Rút ngắn thời gian ký từ "vẽ khung + nhập mật khẩu cho từng trang/từng file" xuống còn "chọn mẫu → chọn danh sách file → nhập mật khẩu 1 lần → chờ xử lý xong".

## 3. Phạm vi (Scope)

### Trong phạm vi (MVP)
- Ký số PDF bằng Digital ID hiện có của người dùng (file `.p12/.pfx`, hoặc Windows Certificate Store — cần xác minh loại nào đang dùng thực tế, xem [06-cau-hoi-mo.md](06-cau-hoi-mo.md)) + mật khẩu, chỉ **1 người ký duy nhất**.
- Hiển thị **ảnh chữ ký tay (PNG)** trong khung ký — đúng như cách hiển thị hiện tại khi ký thủ công trong Acrobat.
- Định nghĩa **template vị trí chữ ký** (tọa độ x, y, width, height, số trang) bằng công cụ vẽ trực quan trên 1 file mẫu, tự động quy đổi tỷ lệ nếu trang thực tế khác kích thước lúc thiết kế.
- Áp dụng 1 template cho hàng loạt file PDF có cùng bố cục (layout) tài liệu, tối đa ~50 file/lần chạy.
- Ký hàng loạt (batch) nhiều file trong 1 lần chạy, nhập mật khẩu 1 lần, ghi đè nếu chạy lại.
- Đây là phần mềm dùng **nội bộ**, không đặt yêu cầu tuân thủ pháp lý về chữ ký điện tử (không cần timestamp/TSA/OCSP).
- Hiển thị tiến trình ký (file nào thành công/thất bại) và log lỗi.
- Xuất file đã ký ra thư mục output riêng (không ghi đè file gốc, hoặc có tuỳ chọn ghi đè).

### Ngoài phạm vi MVP (có thể làm sau)
- Ký bằng USB Token / HSM / ký từ xa (remote signing, VD VNPT SmartCA).
- Tự động nhận diện vị trí ký bằng OCR/AI (không cần vẽ khung thủ công).
- Nhiều template khác nhau áp dụng linh hoạt theo từng file trong cùng 1 batch.
- Quản lý nhiều người dùng, nhiều chứng thư số, phân quyền.
- Ký với timestamp server (TSA) và LTV (Long-Term Validation) — nên cân nhắc đưa vào MVP nếu yêu cầu pháp lý cần (xem mục 6.4).

## 4. Đối tượng người dùng
- Người dùng văn phòng/kế toán/hành chính cần ký số nhiều văn bản PDF có cùng biểu mẫu (hợp đồng, hoá đơn, quyết định, báo cáo...) định kỳ.
- Không yêu cầu kiến thức kỹ thuật — giao diện phải đơn giản, trực quan như thao tác vẽ khung hiện tại.

## 5. Các tài liệu liên quan trong bộ hồ sơ này
- [01-yeu-cau-chuc-nang.md](01-yeu-cau-chuc-nang.md) — Yêu cầu chức năng chi tiết
- [02-yeu-cau-phi-chuc-nang.md](02-yeu-cau-phi-chuc-nang.md) — Yêu cầu phi chức năng, bảo mật
- [03-kien-truc-cong-nghe.md](03-kien-truc-cong-nghe.md) — Đề xuất kiến trúc & công nghệ
- [04-luong-nghiep-vu.md](04-luong-nghiep-vu.md) — Luồng nghiệp vụ & wireframe mô tả
- [05-cau-truc-du-lieu.md](05-cau-truc-du-lieu.md) — Cấu trúc dữ liệu / định dạng file cấu hình
- [06-cau-hoi-mo.md](06-cau-hoi-mo.md) — Câu hỏi còn mở cần quyết định trước khi code
