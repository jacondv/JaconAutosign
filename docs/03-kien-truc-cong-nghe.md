# Đề xuất kiến trúc & công nghệ

> Đã xác nhận với người dùng: chữ ký số dùng file mềm **.p12/.pfx + mật khẩu** (không phải USB Token/HSM), và template vị trí ký là **cố định theo mẫu tài liệu** (không cần vẽ lại cho từng file). Đề xuất dưới đây tối ưu cho 2 điều kiện này; các mục ngoài phạm vi được ghi chú để dễ mở rộng sau.

## 1. So sánh 3 lựa chọn ngôn ngữ

| Tiêu chí | Python | C# (.NET) | JavaScript (Electron/Node) |
|---|---|---|---|
| Thư viện ký PDF chuẩn PAdES, hỗ trợ .p12, incremental update | **pyHanko** — MIT, mã nguồn mở hoàn toàn miễn phí, chủ động thiết kế cho đúng use-case này | **iText7** — mạnh nhất nhưng **AGPL hoặc phải mua license thương mại**; PDFsharp/Syncfusion là lựa chọn khác nhưng yếu hơn về PAdES hoặc cũng trả phí | Không có thư viện thuần JS nào chín muồi tương đương; phải ghép `pdf-lib` + `node-forge`/`node-signpdf` — rủi ro về tuân thủ chuẩn và ít được kiểm chứng |
| Render trang PDF thành ảnh để vẽ khung | `pypdfium2` (Apache-2.0/BSD, miễn phí, dựa trên PDFium của Chromium) | `PDFium` qua binding, hoặc `iText7` tự render | `pdf.js` (Mozilla, MIT) — rất tốt, đây là điểm mạnh của JS |
| Dựng UI desktop vẽ hình chữ nhật kéo-thả | PySide6 (Qt, LGPL) hoặc Tkinter (có sẵn) | WPF/WinForms (native Windows, rất mượt) | Electron + HTML Canvas (dễ làm UI đẹp nhưng nặng, đóng gói ~150-200MB) |
| Đóng gói thành .exe độc lập | PyInstaller — ổn định, quen thuộc | `dotnet publish` self-contained — native, nhẹ, khởi động nhanh | `electron-builder` — được nhưng file cài đặt nặng |
| Chi phí giấy phép | **0đ** (toàn bộ thư viện đề xuất đều miễn phí, không AGPL) | 0đ nếu chấp nhận AGPL (rủi ro pháp lý khi phân phối nội bộ), hoặc tốn phí nếu mua license iText/Syncfusion | 0đ nhưng chất lượng chữ ký số khó đảm bảo bằng 2 lựa chọn kia |
| Độ chín cho đúng bài toán "ký số hàng loạt" | **Cao nhất** — pyHanko có sẵn API `sign_pdf`, hỗ trợ batch, PAdES B-B/B-T/B-LT/B-LTA, visible signature, sẵn cả CLI tham khảo | Cao nếu chấp nhận chi phí iText | Trung bình — cần tự xây nhiều phần |

**Khuyến nghị: Python**, vì bài toán cốt lõi (ký số PDF đúng chuẩn, hàng loạt, không tốn phí license) được giải quyết trọn vẹn bởi **pyHanko**, vốn được thiết kế chính xác cho mục đích này.

## 2. Stack đề xuất (MVP)

| Thành phần | Lựa chọn | Vai trò |
|---|---|---|
| Ngôn ngữ | Python 3.11+ | |
| Ký số PDF (PAdES) | [`pyHanko`](https://github.com/MatthiasValvekens/pyHanko) (MIT) | Đọc `.p12`, tạo chữ ký số PKCS#7 nhúng theo chuẩn PAdES, hỗ trợ incremental update (ký nhiều lần không phá chữ ký cũ), hỗ trợ timestamp (TSA) nếu cần sau này |
| Render PDF → ảnh xem trước | [`pypdfium2`](https://github.com/pypdfium2-team/pypdfium2) (Apache-2.0/BSD) | Hiển thị trang PDF lên canvas để người dùng vẽ khung khi tạo template |
| Đọc thông tin trang PDF (số trang, kích thước, xoay) | `pypdfium2` hoặc `pypdf` (BSD) | Dùng khi validate file trước khi ký (F3.4) |
| Giao diện desktop | [`PySide6`](https://doc.qt.io/qtforpython/) (LGPLv3 — dùng được cho phần mềm đóng gói/nội bộ mà không bắt buộc mở mã nguồn) | Màn hình thiết kế template (vẽ khung), màn hình chọn file & chạy batch, thanh tiến trình |
| Đóng gói .exe | `PyInstaller` | Xuất bản `.exe` chạy độc lập trên Windows, không cần cài Python |
| Lưu cấu hình template | File JSON cục bộ (xem [05-cau-truc-du-lieu.md](05-cau-truc-du-lieu.md)) | |
| Xử lý song song (tuỳ chọn) | `concurrent.futures.ThreadPoolExecutor`, giới hạn 2-4 luồng | Tăng tốc ký hàng loạt, vẫn an toàn vì mỗi file xử lý độc lập |

> Lưu ý licensing: **tránh dùng PyMuPDF (`fitz`)** cho phần render — thư viện này chuyển sang giấy phép **AGPL/thương mại** từ Artifex, dùng trong app đóng gói phân phối có thể phát sinh nghĩa vụ mở mã nguồn hoặc chi phí license. `pypdfium2` là lựa chọn thay thế tương đương về tính năng render, giấy phép permissive (Apache-2.0/BSD), không có ràng buộc này.

## 3. Kiến trúc phần mềm (3 lớp, tách rời rõ ràng)

```
┌─────────────────────────────────────────────────────────┐
│                      UI Layer (PySide6)                  │
│  - Màn hình Template Designer (vẽ khung trên ảnh trang)  │
│  - Màn hình Batch Runner (chọn file, chọn template,      │
│    nhập mật khẩu, xem tiến trình)                        │
│  - Màn hình Kết quả / Báo cáo                             │
└───────────────────────┬───────────────────────────────────┘
                         │ gọi qua các service, không thao tác PDF trực tiếp
┌───────────────────────▼───────────────────────────────────┐
│                  Application/Domain Layer                 │
│  - TemplateService: tạo/lưu/đọc template JSON              │
│  - PdfInspectService: đọc số trang, kích thước, validate   │
│    file trước khi ký (dùng pypdfium2/pypdf)                │
│  - BatchSignService: điều phối vòng lặp ký nhiều file,     │
│    gom kết quả, gọi SigningEngine cho từng file            │
└───────────────────────┬───────────────────────────────────┘
                         │
┌───────────────────────▼───────────────────────────────────┐
│                  Signing Engine (pyHanko wrapper)          │
│  - Load .p12 + mật khẩu (1 lần, giữ trong RAM)              │
│  - Với mỗi file: map template (trang, toạ độ) → PDF thật,   │
│    tạo appearance chữ ký, ký PAdES, ghi ra file output      │
│  - Xử lý lỗi từng file, không crash toàn batch              │
└─────────────────────────────────────────────────────────────┘
```

Tách lớp như trên để sau này nếu đổi sang USB Token/HSM/ký từ xa, chỉ cần viết lại **Signing Engine**, không đụng vào UI hay Template Service.

## 3b. Nguồn Digital ID (Certificate Provider)

> **Đã xác minh**: Digital ID thực tế của người dùng là file **`.pfx`** — cùng chuẩn PKCS#12 với `.p12`, tái sử dụng trực tiếp được, không cần tạo mới (xem [06-cau-hoi-mo.md](06-cau-hoi-mo.md)). **MVP chỉ cần 1 nhánh duy nhất: PKCS#12 file**, dùng `pyhanko.sign.signers.SimpleSigner.load_pkcs12(path, passphrase)` — thư viện đọc được cả đuôi `.pfx` lẫn `.p12` vì nội dung định dạng giống hệt nhau.

Vẫn nên định nghĩa Signing Engine qua 1 interface `CertificateProvider` nhỏ (dù MVP chỉ có 1 cài đặt `Pkcs12CertificateProvider`), để nếu sau này đổi sang nguồn khác (Windows Certificate Store, USB Token/PKCS#11...) chỉ cần thêm cài đặt mới, không sửa UI hay Batch Service. Không cần code các nhánh này ngay — ghi chú lại để không phải thiết kế lại kiến trúc nếu có nhu cầu về sau:

| Nguồn (không cần code cho MVP) | Cách đọc trong Python | Khi nào cần |
|---|---|---|
| Windows Certificate Store (Personal/"My") | `wincertstore`/`pywin32` (`win32crypt`) lấy handle CNG/CryptoAPI, ký digest qua `NCryptSignHash`, ghép vào cấu trúc PDF bằng API cấp thấp của pyHanko | Nếu sau này đổi Digital ID sang lưu trong Windows thay vì file rời |
| PKCS#11 (USB Token/thẻ) | `pyhanko.sign.pkcs11.PKCS11Signer` (có sẵn trong pyHanko) | Nếu sau này đổi sang chữ ký bằng token cứng |

## 4. Điểm kỹ thuật cần lưu ý khi hiện thực

### 4.1. Ánh xạ toạ độ khung vẽ ↔ toạ độ PDF thật
- Khi người dùng vẽ khung trên ảnh preview (đơn vị pixel, theo DPI render), phải quy đổi sang **toạ độ PDF (point, hệ trục gốc dưới-trái)** để lưu vào template — không lưu theo pixel vì các file khác nhau có thể render ở DPI khác nhau.
- Cần xử lý đúng trang bị **xoay (rotate 90/180/270°)** và **kích thước khác chuẩn** (không phải A4) — lấy kích thước/rotation từ chính file đang áp template, không giả định cố định.

### 4.2. Trang "đầu/cuối" khi số trang file khác nhau
- Vì các file trong batch có thể khác số trang, template nên lưu vị trí ký theo kiểu tham chiếu linh hoạt: `first`, `last`, hoặc số trang tuyệt đối `page: 3` — logic áp dụng phải resolve đúng trang thật của từng file khi chạy (chi tiết ở [05-cau-truc-du-lieu.md](05-cau-truc-du-lieu.md)).

### 4.3. Ký nhiều chữ ký trên nhiều trang của cùng 1 file
- Nếu template có chữ ký ở nhiều trang (VD trang 1 và trang cuối), pyHanko cần ký **tuần tự bằng incremental update**: lần ký sau không được làm hỏng chữ ký trước trong cùng file. Cần dùng đúng API hỗ trợ nhiều `signature field` hoặc ký nối tiếp (chain signing) của pyHanko.

### 4.4. Quản lý mật khẩu trong phiên làm việc
- Mật khẩu `.p12` nhập 1 lần, giữ trong biến ở bộ nhớ trong suốt vòng đời batch, dùng xong nên xoá tham chiếu để giải phóng. Không truyền mật khẩu qua tham số dòng lệnh (visible trong process list) nếu có phần xử lý subprocess.

### 4.5. Đóng gói .exe
- PyInstaller cần khai báo rõ các file dữ liệu đi kèm (icon, font chữ ký nếu có).
- Nên build ở chế độ `--onedir` (khởi động nhanh hơn `--onefile`) trừ khi yêu cầu 1 file duy nhất để phát tán.
- Kiểm thử .exe trên máy Windows "sạch" (không có Python) trước khi phát hành.

## 5. Phương án thay thế (nếu sau này đổi hướng)

- **C# + iText7**: cân nhắc nếu tổ chức sẵn sàng mua license thương mại của iText, hoặc xác nhận việc dùng nội bộ (không phân phối ra ngoài) chấp nhận được theo AGPL sau khi tham vấn pháp lý. Đổi lại được UI native Windows (WPF) mượt hơn và hiệu năng khởi động nhanh hơn.
- **JS/Electron**: chỉ nên cân nhắc nếu nhóm phát triển đã có sẵn kinh nghiệm Electron và chấp nhận đầu tư nhiều hơn cho phần ký số đúng chuẩn (ghép `pdf-lib` + `node-forge`, tự viết phần PAdES, khó đảm bảo tương thích Adobe Reader/trình kiểm tra chữ ký số của cơ quan nhà nước).

## 6. Nguồn tham khảo đã tra cứu khi soạn tài liệu này
- [pyHanko GitHub](https://github.com/MatthiasValvekens/pyHanko) — MIT License, hỗ trợ PAdES B-B/B-T/B-LT/B-LTA, `SimpleSigner.load_pkcs12()`, PKCS#11.
- [pyHanko signing docs](https://docs.pyhanko.eu/en/latest/lib-guide/signing.html)
- [iText AGPLv3 license page](https://itextpdf.com/how-buy/AGPLv3-license) — xác nhận mô hình dual-license AGPL/thương mại.
- [PyMuPDF licensing thảo luận](https://github.com/pymupdf/PyMuPDF/discussions/971) và bài phân tích [MIT-Licensed PyMuPDF Alternative](https://docs.bswen.com/blog/2026-03-04-pymupdf-mit-alternative-commercial/) — lý do khuyến nghị dùng `pypdfium2` thay vì `PyMuPDF`.
