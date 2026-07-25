# Yêu cầu chức năng chi tiết

## F1. Quản lý chứng thư số / Digital ID (Certificate)

Ứng dụng chỉ phục vụ **1 người ký duy nhất** (không cần quản lý nhiều danh tính cùng lúc), nhưng cần hỗ trợ **đúng nguồn Digital ID mà Adobe Acrobat đang hỗ trợ**, vì hiện chưa xác định chắc chắn Digital ID hiện tại của người dùng ở định dạng nào (xem [06-cau-hoi-mo.md](06-cau-hoi-mo.md) mục 1). Thiết kế theo dạng **có thể chọn nguồn** (Certificate Provider), tối thiểu 2 nguồn phổ biến nhất trong MVP:

- F1.1a. **Nguồn file PKCS#12** (`.p12`/`.pfx`) — chọn file từ máy tính, nhập mật khẩu để mở.
- F1.1b. **Nguồn Windows Certificate Store** (Personal/"My" store của user hiện tại) — liệt kê các chứng thư số có sẵn trong Windows (giống danh sách Acrobat hiển thị ở "Digital ID from a Windows Certificate Store"), chọn 1 cái, nhập PIN/mật khẩu nếu được yêu cầu bởi CSP.
- F1.1c. (Mở rộng sau, không bắt buộc MVP) **PKCS#11** (USB Token/thẻ cứng) — vì kiến trúc đã tách riêng Signing Engine (xem [03-kien-truc-cong-nghe.md](03-kien-truc-cong-nghe.md)) nên có thể bổ sung sau mà không sửa UI.
- F1.2. Nhập mật khẩu để mở/kiểm tra Digital ID (validate ngay khi nhập, báo lỗi rõ nếu sai mật khẩu hoặc file hỏng).
- F1.3. Hiển thị thông tin chứng thư số sau khi mở thành công: Chủ thể (Subject/CN), Tổ chức cấp (Issuer), Ngày hết hạn — để người dùng xác nhận đúng chữ ký trước khi ký hàng loạt.
- F1.4. Cảnh báo nếu chứng thư số sắp hết hạn hoặc đã hết hạn (chặn ký, báo lỗi rõ ràng) — chỉ là cảnh báo thông tin, không phải yêu cầu tuân thủ pháp lý (phần mềm dùng nội bộ, xem [02-yeu-cau-phi-chuc-nang.md](02-yeu-cau-phi-chuc-nang.md)).
- F1.5. **Không lưu mật khẩu ra đĩa** dưới bất kỳ hình thức nào.
- F1.6. (Tuỳ chọn) Ghi nhớ đường dẫn file .p12 gần nhất hoặc chứng thư đã chọn trong Windows Store lần trước (không nhớ mật khẩu) để tiện chọn lại lần sau.

## F2. Tạo & quản lý Template vị trí chữ ký
- F2.1. Cho phép mở 1 file PDF mẫu (đại diện cho layout của cả lô file sẽ ký) để thiết kế template.
- F2.2. Hiển thị PDF mẫu dưới dạng ảnh xem trước (render từng trang) để người dùng thao tác vẽ.
- F2.3. Cho phép **vẽ hình chữ nhật** bằng chuột lên trang để xác định vùng đặt chữ ký (giữ trải nghiệm quen thuộc).
- F2.4. Cho phép chỉnh sửa khung đã vẽ: kéo di chuyển, resize, xoá.
- F2.5. Cho phép định nghĩa **nhiều vùng ký trên nhiều trang khác nhau** trong cùng 1 template (VD: trang 1 ký "Người lập", trang cuối ký "Người duyệt").
- F2.6. Hỗ trợ chỉ định trang theo:
  - Số trang tuyệt đối (trang 1, trang 3...).
  - Vị trí tương đối: "trang đầu tiên", "trang cuối cùng" — quan trọng vì các file trong batch có thể có **số trang khác nhau** dù cùng layout khung ký ở trang cuối.
- F2.7. Lưu template thành file cấu hình (JSON) có thể đặt tên, tái sử dụng cho các lần ký sau (xem [05-cau-truc-du-lieu.md](05-cau-truc-du-lieu.md)).
- F2.8. Quản lý danh sách template đã lưu: xem, đổi tên, xoá, nhân bản (duplicate) để chỉnh sửa thành template mới.
- F2.9. Cấu hình nội dung hiển thị trong khung ký: **mặc định chỉ hiển thị ảnh chữ ký tay** (người dùng chọn 1 file ảnh PNG nền trong suốt — đúng như cách đang dùng trong Acrobat hiện tại), có thể bật thêm text phụ (tên, ngày ký) nếu muốn nhưng không bắt buộc.

## F3. Chọn danh sách file cần ký hàng loạt
- F3.1. Cho phép chọn nhiều file PDF cùng lúc (chọn nhiều file, hoặc chọn cả thư mục — quét toàn bộ .pdf trong thư mục, có tuỳ chọn bao gồm thư mục con).
- F3.2. Hiển thị danh sách file đã chọn: tên file, số trang, đường dẫn, trạng thái.
- F3.3. Cho phép loại bỏ bớt file khỏi danh sách trước khi ký.
- F3.4. Cảnh báo/đánh dấu các file có số trang **ít hơn** số trang mà template yêu cầu (VD template ký ở "trang 3" nhưng file chỉ có 2 trang) — để người dùng biết trước sẽ lỗi, tránh ký dở dang.
- F3.5. Cho phép xem trước (preview) khung ký sẽ được áp lên 1 file cụ thể trong danh sách trước khi chạy hàng loạt, để xác nhận vị trí đúng.

## F4. Thực thi ký hàng loạt (Batch Sign)
- F4.1. Người dùng chọn: Template đã lưu + Danh sách file + Chứng thư số → bấm "Bắt đầu ký".
- F4.2. Nhập mật khẩu chứng thư số **đúng 1 lần** cho toàn bộ batch (giữ trong bộ nhớ phiên làm việc, không ghi ra đĩa).
- F4.3. Xử lý tuần tự (hoặc song song có giới hạn) từng file: áp khung chữ ký của template vào đúng trang, ký số, xuất file kết quả.
- F4.4. Hiển thị tiến trình real-time: X/N file đã xử lý, thanh tiến trình, file đang xử lý hiện tại.
- F4.5. Với mỗi file, hiển thị trạng thái: Thành công / Lỗi (kèm lý do ngắn gọn, VD "thiếu trang", "file bị khoá", "PDF hỏng").
- F4.6. Không dừng toàn bộ batch khi 1 file lỗi — tiếp tục xử lý các file còn lại, tổng kết báo cáo lỗi ở cuối.
- F4.7. Cho phép huỷ (Cancel) giữa chừng.
- F4.8. Xuất file đã ký vào thư mục output cấu hình được (mặc định: thư mục con `signed/` cạnh file gốc, hoặc thư mục do người dùng chỉ định), **giữ nguyên tên file gốc** (không thêm hậu tố).
- F4.9. Sau khi hoàn tất: hiển thị báo cáo tổng kết (số file thành công/thất bại) và cho phép xuất báo cáo dạng log/CSV.
- F4.10. Nếu chạy lại batch và file output đã tồn tại (cùng tên) trong thư mục output — **ghi đè trực tiếp**, không hỏi xác nhận lại (theo xác nhận của người dùng — đây là phần mềm nội bộ, ưu tiên tốc độ thao tác).

## F5. Xem lại / kiểm tra kết quả
- F5.1. Cho phép mở nhanh file đã ký (mở bằng ứng dụng PDF mặc định của hệ điều hành) ngay từ danh sách kết quả để kiểm tra.
- F5.2. Hiển thị rõ trong báo cáo: đường dẫn file gốc → đường dẫn file đã ký.

## F6. (Tuỳ chọn giai đoạn sau) Lịch sử & log
- F6.1. Lưu log các lần chạy batch (thời gian, số file, người ký, template dùng) phục vụ tra cứu/đối soát sau này.
- F6.2. Không log mật khẩu hay nội dung nhạy cảm.
