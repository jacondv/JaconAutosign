# Cấu trúc dữ liệu / Định dạng file cấu hình

## 1. File Template (JSON)

Lưu tại `templates/<ten-template>.json`. Toạ độ theo hệ **PDF point** (1 point = 1/72 inch), gốc toạ độ **(0,0) ở góc dưới-trái** của trang (chuẩn PDF), **không dùng pixel** để không phụ thuộc DPI render.

```json
{
  "template_id": "hop-dong-lao-dong-v1",
  "template_name": "Hợp đồng lao động - chữ ký giám đốc",
  "created_at": "2026-07-25T10:00:00+07:00",
  "source_sample_file": "samples/hop_dong_mau.pdf",
  "signature_boxes": [
    {
      "box_id": "sig-giam-doc",
      "label": "Chữ ký Giám đốc",
      "page_ref": {
        "type": "absolute",
        "page_number": 1
      },
      "rect": {
        "x": 350.0,
        "y": 120.0,
        "width": 150.0,
        "height": 60.0
      },
      "page_size_at_design_time": {
        "width": 595.28,
        "height": 841.89,
        "rotation": 0
      },
      "appearance": {
        "image_path": "signatures/chuky_tay.png",
        "show_text": false,
        "text_template": null
      }
    },
    {
      "box_id": "sig-nguoi-lap",
      "label": "Chữ ký người lập (trang cuối)",
      "page_ref": {
        "type": "last"
      },
      "rect": {
        "x": 60.0,
        "y": 80.0,
        "width": 150.0,
        "height": 60.0
      },
      "page_size_at_design_time": {
        "width": 595.28,
        "height": 841.89,
        "rotation": 0
      },
      "appearance": {
        "image_path": "signatures/chuky_tay.png",
        "show_text": false,
        "text_template": null
      }
    }
  ]
}
```

> `appearance.image_path` là **mặc định chính** (ảnh chữ ký tay PNG nền trong suốt, đúng như cách đang dùng trong Acrobat hiện tại) — `show_text`/`text_template` chỉ bật thêm khi cần, không bắt buộc.

### Giải thích các trường quan trọng

- `page_ref.type`: `"absolute"` (dùng kèm `page_number`, đánh số từ 1) | `"first"` | `"last"` | (mở rộng sau: `"last_minus_n"` cho "trang áp chót" v.v.)
- `rect`: toạ độ **góc dưới-trái** của khung (chuẩn PDF) + width/height, đơn vị point.
- `page_size_at_design_time`: kích thước trang **lúc thiết kế template**, dùng để hệ thống tự động **quy đổi tỉ lệ** nếu file thực tế trong batch có kích thước trang khác (VD template thiết kế trên A4 nhưng 1 file trong batch là Letter) — xem mục 2 bên dưới. Nếu không muốn tự quy đổi, ứng dụng có thể cảnh báo thay vì tự scale (quyết định UX cụ thể — xem [06-cau-hoi-mo.md](06-cau-hoi-mo.md)).
- `appearance.image_path`: đường dẫn ảnh chữ ký tay (PNG nền trong suốt) — **mặc định dùng cho mọi template**, đây là nội dung hiển thị chính trong khung ký.
- `appearance.text_template`: (tuỳ chọn, tắt mặc định) chuỗi hiển thị thêm kèm hình chữ ký, hỗ trợ biến `{{signer_name}}`, `{{sign_date}}`.

## 2. Quy tắc resolve toạ độ khi áp template lên file thực tế

1. Xác định trang thật cần ký dựa trên `page_ref` (VD `last` → trang cuối cùng của file đang xử lý, không phải trang cuối của file mẫu).
2. Lấy kích thước & rotation thật của trang đó trong file đang ký.
3. Nếu kích thước khác với `page_size_at_design_time` → quy đổi toạ độ theo tỷ lệ (scale theo width/height), đảm bảo khung vẫn nằm đúng vị trí tương đối trên trang (VD "cách mép phải 2cm, cách đáy 3cm" thay vì toạ độ tuyệt đối cứng) — **cách tính theo tỷ lệ tương đối cần thống nhất khi code**, xem câu hỏi mở.
4. Nếu trang có `rotation` khác 0 (90/180/270°) → xoay hệ toạ độ khung tương ứng trước khi ghi vào PDF, để chữ ký hiển thị đúng chiều khi xem.
5. Nếu trang thật không tồn tại (file thiếu trang so với `page_number` tuyệt đối) → trả lỗi rõ ràng cho file đó (xem F3.4 / F4.5), không cố ký sai vị trí.

## 3. Cấu hình ứng dụng chung (settings.json)

```json
{
  "last_p12_path": "C:\\Users\\...\\chungthu.p12",
  "default_output_folder_mode": "subfolder",
  "default_output_subfolder_name": "signed",
  "default_dpi_preview": 150,
  "max_parallel_signing": 2,
  "language": "vi"
}
```

> Không bao giờ lưu mật khẩu ở đây, kể cả mã hoá — xem [02-yeu-cau-phi-chuc-nang.md](02-yeu-cau-phi-chuc-nang.md) mục 1.

## 4. Báo cáo kết quả batch (xuất CSV, ví dụ cấu trúc cột)

| file_name | file_path | status | error_reason | signed_output_path | pages_signed | signed_at |
|---|---|---|---|---|---|---|
| hopdong_001.pdf | D:\input\hopdong_001.pdf | success | | D:\input\signed\hopdong_001.pdf | 1,4 | 2026-07-25T10:05:12+07:00 |
| hopdong_002.pdf | D:\input\hopdong_002.pdf | failed | thiếu trang (cần trang 3, file có 2 trang) | | | |
