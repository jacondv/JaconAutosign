# Yêu cầu phi chức năng & Bảo mật

## 1. Bảo mật (quan trọng nhất)

- **Không ghi mật khẩu chứng thư số ra đĩa** (không log, không cache, không lưu trong file config/registry) dưới mọi hình thức, kể cả khi "ghi nhớ mật khẩu" — nếu có tính năng này ở giai đoạn sau, bắt buộc phải mã hoá bằng cơ chế bảo mật của hệ điều hành (Windows DPAPI / Credential Manager), không tự chế cơ chế mã hoá.
- Mật khẩu chỉ giữ trong **bộ nhớ RAM của tiến trình đang chạy**, trong thời gian batch đang xử lý; xoá khỏi bộ nhớ (zero-out biến) ngay sau khi dùng xong hoặc khi ứng dụng đóng.
- Không log nội dung file PDF, không log mật khẩu, không log private key. Log chỉ chứa: tên file, timestamp, trạng thái, mã lỗi.
- File chứng thư số `.p12/.pfx` không được copy/di chuyển đi nơi khác — chỉ đọc tại đường dẫn người dùng chỉ định.
- Nếu ứng dụng có thành phần chạy nền/server cục bộ (local service), phải chỉ lắng nghe trên `localhost`, không mở cổng ra mạng ngoài.
- Không gửi file PDF hoặc chứng thư số lên bất kỳ server bên ngoài nào — toàn bộ xử lý ký phải diễn ra **cục bộ (local)** trên máy người dùng (trừ khi sau này chủ động chuyển sang phương án ký từ xa/HSM — cần thiết kế lại phần bảo mật riêng).
- Kiểm tra toàn vẹn PDF trước khi ký (phát hiện file PDF bị hỏng/mã hoá bằng mật khẩu mở file) và báo lỗi rõ ràng thay vì crash.

## 2. Tính đúng đắn của chữ ký (phần mềm nội bộ — không đặt nặng tuân thủ pháp lý)

> Xác nhận từ người dùng: đây là phần mềm dùng **nội bộ**, mục tiêu là thay thế thao tác thủ công (vẽ khung + nhập mật khẩu + dán ảnh chữ ký tay trong Acrobat), **không cần tuân thủ các quy định pháp lý về chữ ký điện tử** (VD không bắt buộc timestamp/TSA, không bắt buộc kiểm tra OCSP/CRL). Mục 2 dưới đây chỉ là các lưu ý **kỹ thuật** để chữ ký hiển thị đúng và file PDF không bị hỏng, không phải yêu cầu tuân thủ.

- Vẫn nên chèn chữ ký theo đúng cơ chế chữ ký số PDF chuẩn (PKCS#7/CMS nhúng trong PDF qua `.p12`/Windows Certificate Store) thay vì chỉ dán ảnh tĩnh đè lên PDF (flatten ảnh) — vì đây chính xác là cách Acrobat đang làm (vẽ khung → nhập mật khẩu → Acrobat tự ký bằng chứng thư số, hiển thị ảnh chữ ký tay làm appearance). Giữ đúng cơ chế này để file vẫn mở được trong Acrobat và thấy chữ ký hợp lệ như trước giờ, dù không cần thêm timestamp/TSA.
- Hình ảnh chữ ký tay hiển thị trên khung vẽ phải đúng vị trí/kích thước người dùng đã vẽ trong template, không lệch toạ độ giữa các trang có kích thước khác nhau (A4 vs Letter, trang xoay ngang/dọc) — tự động quy đổi tỷ lệ theo kích thước trang thật (đã xác nhận với người dùng, xem [05-cau-truc-du-lieu.md](05-cau-truc-du-lieu.md)).
- Khi 1 PDF đã có chữ ký số từ trước (ký lần 2 trên trang khác - đồng ký), chữ ký mới phải là **incremental update** (không phá vỡ chữ ký cũ đã có trong file) — đây là điểm kỹ thuật quan trọng cần thư viện hỗ trợ tốt (pyHanko hỗ trợ sẵn).

## 3. Hiệu năng
- Xử lý tốt batch **tối đa khoảng 50 file PDF** mỗi lần chạy (con số thực tế theo xác nhận của người dùng) mà không treo ứng dụng (xử lý bất đồng bộ / chạy nền, UI không bị đơ — hiển thị tiến trình). Không cần tối ưu cho quy mô lớn hơn (hàng trăm file) ở MVP.
- Thời gian ký 1 file (vài trang, dưới 10MB) không quá vài giây (không tính thời gian I/O đĩa chậm).
- Với quy mô ~50 file/batch, xử lý **tuần tự đơn giản là đủ**; xử lý song song (2-4 luồng) là tối ưu tuỳ chọn, không bắt buộc cho MVP.

## 4. Độ tin cậy
- Nếu ứng dụng bị tắt đột ngột giữa batch, các file đã ký thành công trước đó phải giữ nguyên vẹn (không hỏng); có thể chạy lại phần còn thiếu.
- Không được để file gốc bị hỏng/mất dữ liệu trong bất kỳ trường hợp lỗi nào (luôn ghi ra file/đường dẫn output riêng biệt, không ghi đè trực tiếp lên file gốc trừ khi người dùng chủ động chọn ghi đè và đã có cảnh báo).

## 5. Khả năng dùng lại / bảo trì
- Template lưu dạng file cấu hình rõ ràng (JSON — xem [05-cau-truc-du-lieu.md](05-cau-truc-du-lieu.md)), để người dùng có thể chia sẻ template giữa các máy hoặc backup.
- Kiến trúc tách rời rõ 3 lớp: (1) UI thao tác vẽ khung & chọn file, (2) Logic xử lý PDF (tìm trang, chèn appearance), (3) Logic ký số (PKCS#12, PKCS#7) — để dễ thay đổi/nâng cấp từng phần sau này (VD sau này đổi sang USB Token chỉ cần thay lớp (3)).

## 6. Khả năng triển khai
- Đóng gói thành ứng dụng chạy trên **Windows** (môi trường làm việc hiện tại là Windows 11), dạng cài đặt đơn giản hoặc portable (không cần cài Python/Node riêng nếu người dùng cuối không rành kỹ thuật) — ưu tiên đóng gói thành file `.exe` độc lập.
- Giao diện tiếng Việt.

## 7. Khả năng phục hồi khi lỗi từng file
- Lỗi ở 1 file (thiếu trang, PDF bị mã hoá, sai định dạng...) không được làm crash toàn bộ ứng dụng hoặc dừng batch — phải bắt lỗi (exception) ở mức từng file, ghi nhận và tiếp tục.
