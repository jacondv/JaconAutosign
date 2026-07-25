# Câu hỏi mở & quyết định cần chốt trước/trong khi code

## Đã chốt (theo xác nhận của người dùng ngày 2026-07-25)

| # | Câu hỏi | Quyết định |
|---|---|---|
| 1 | Pháp lý (Nghị định 23/2025/NĐ-CP, timestamp/TSA, OCSP...) | **Bỏ qua** — phần mềm dùng nội bộ, không cần tuân thủ pháp lý về chữ ký điện tử. Xem [02-yeu-cau-phi-chuc-nang.md](02-yeu-cau-phi-chuc-nang.md) mục 2. |
| 2 | Quy tắc đặt tên file output | Giữ **nguyên tên file gốc**. |
| 3 | Ký lại (re-run) file đã ký | **Ghi đè** file output cũ, không hỏi lại. |
| 4 | PDF đầu vào có mật khẩu mở file không | **Không** — tất cả file input đều không có mật khẩu, không cần xử lý PDF mã hoá. |
| 5 | Quy mô batch | Tối đa khoảng **50 file/lần** — không cần tối ưu cho quy mô lớn hơn ở MVP. |
| 6 | Hệ điều hành máy chạy | **Windows**. |
| 7 | Số người ký / số chứng thư số | **Chỉ 1 người ký** (1 danh tính) cho toàn bộ batch. |
| 8 | Nội dung hiển thị trong khung ký | **Ảnh chữ ký tay** (file PNG, đúng như đang dùng trong Acrobat hiện tại) — không cần text, không cần "chữ ký điện tử đúng nghĩa pháp lý" phức tạp. |
| 9 | Quy tắc khi kích thước trang khác template | **Tự động quy đổi tỷ lệ (scale)** theo kích thước trang thật. |
| 10 | Cách app can thiệp vào việc ký | App **tự ký độc lập** bằng thư viện Python (pyHanko), không điều khiển/tự động hoá Acrobat. Vẫn phải cho ra kết quả **tương đương với cách Acrobat đang ký** (chèn khung tại vị trí vẽ, nhập mật khẩu, hiển thị ảnh chữ ký tay) để file mở lại trong Acrobat vẫn thấy đúng như hiện tại. |

## Đã chốt thêm (2026-07-25, sau khi kiểm tra Digital ID thực tế)

| # | Câu hỏi | Quyết định |
|---|---|---|
| 11 | Định dạng Digital ID thực tế | Là file **`.pfx`** — về bản chất là **cùng chuẩn PKCS#12 với `.p12`**, chỉ khác đuôi file. Người dùng đã có sẵn file này. |
| 12 | Có cần tạo Digital ID mới không | **Không** — tái sử dụng trực tiếp file `.pfx` hiện có, đọc bằng `SimpleSigner.load_pkcs12()` của pyHanko (thư viện đọc được cả `.pfx` lẫn `.p12`, không cần đổi tên/chuyển đổi gì). |

→ **MVP chỉ cần implement đúng 1 nhánh `CertificateProvider`: PKCS#12 file (`.p12`/`.pfx`)**. Nhánh Windows Certificate Store và PKCS#11 nêu ở [03-kien-truc-cong-nghe.md](03-kien-truc-cong-nghe.md) mục 3b **không cần code cho MVP** — chỉ giữ lại như ghi chú kiến trúc mở rộng nếu sau này đổi loại Digital ID khác.

## Còn mở

### 1. Ảnh chữ ký tay dùng chung hay đổi theo template?
Giả định hiện tại: 1 ảnh chữ ký tay (PNG) dùng chung cho mọi khung ký trong mọi template (vì chỉ có 1 người ký). Nếu có nhu cầu đổi ảnh khác nhau theo từng khung/template (hiếm khi cần với 1 người ký) thì cần xác nhận thêm.

---

**Gợi ý cách dùng bộ tài liệu này với AI code**: đưa toàn bộ thư mục `docs/` vào ngữ cảnh, yêu cầu AI đọc hết trước khi code. Việc đầu tiên nên làm là xác minh mục "Còn mở #1" ở trên (loại Digital ID thực tế), vì nó quyết định độ phức tạp và phạm vi code của Signing Engine.
