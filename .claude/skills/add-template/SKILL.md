---
name: add-template
description: Thêm hoặc sửa template meme cho Easy Meme — đặt ảnh, viết JSON khung chữ (toạ độ 0–1, style, max_lines, max_chars, hint, when_to_use, ví dụ), kiểm tra khung và tràn chữ bằng ảnh xem trước, cập nhật embedding và chạy test. Dùng khi người dùng muốn thêm template mới, chỉnh khung chữ, hoặc meme của một template hay bị tràn chữ hay chọn sai.
argument-hint: "<template-id> [đường dẫn ảnh]"
---

# Thêm template meme

Mỗi template = `backend/data/templates/<id>.json` + ảnh trong `backend/data/templates/images/`. `load_templates()` chỉ nạp template có `enabled: true` và có ảnh.

## 1. Ảnh

- Nguồn ảnh: ưu tiên ảnh người dùng tự chụp/vẽ, CC0, hoặc vẽ bằng code như `backend/scripts/make_templates.py`. Ảnh meme phổ biến có bản quyền: chỉ dùng khi người dùng chấp nhận, ghi rõ nguồn vào `source`.
- Để khoảng trống cho chữ (dải trắng phía trên cho style `caption`, vùng thoáng cho `impact`). Cạnh dài tối đa nên ~720–1080 px.
- `id`: chữ thường, số, gạch ngang (ví dụ `cat-surprised`); trùng tên file JSON.

## 2. JSON

```json
{
  "id": "cat-surprised",
  "name": "Mèo ngạc nhiên",
  "image": "cat-surprised.png",
  "boxes": [
    {"id": "top", "x": 0.03, "y": 0.02, "w": 0.94, "h": 0.16, "style": "impact", "max_lines": 2, "max_chars": 36, "hint": "tình huống bất ngờ"},
    {"id": "bottom", "x": 0.03, "y": 0.82, "w": 0.94, "h": 0.16, "style": "impact", "max_lines": 2, "max_chars": 36, "hint": "phản ứng"}
  ],
  "when_to_use": "Bất ngờ, sốc nhẹ trước một sự thật hiển nhiên mà mình không biết",
  "examples": [{"top": "Khi biết lương tháng này", "bottom": "Đã trừ bảo hiểm"}],
  "tags": ["bất ngờ", "sốc", "ngạc nhiên"],
  "source": "Ảnh tự chụp",
  "enabled": true
}
```

- `x, y, w, h`: tỉ lệ 0–1 theo kích thước ảnh, gốc ở góc trên trái.
- `style`: `impact` (chữ trắng viền đen, in hoa, font Anton), `caption` (chữ đen trên nền sáng), `label` (chữ trắng viền đen, giữ hoa thường, cho nhãn nhỏ).
- `hint` cho LLM biết vai trò từng khung; `when_to_use`, `tags`, `examples` quyết định template có được tìm thấy không (hybrid search). Viết theo **ý nghĩa tình huống**, đừng mô tả hình.
- Ví dụ phải có đủ đúng các box id. Có thể dùng `\n` để xuống dòng chủ động.

## 3. Kiểm tra

```bash
cd backend && .venv/bin/python ../.claude/skills/add-template/scripts/check_template.py <id> --out "$SCRATCH"
```

Mở ảnh `<id>-check.png` bằng Read: ảnh đầu có khung đỏ vẽ đè để chỉnh toạ độ, các ảnh sau là ví dụ và câu dài đúng `max_chars`. Sửa JSON và chạy lại tới khi script báo "Không phát hiện vấn đề". Tràn chữ thì nới khung hoặc giảm `max_chars`.

## 4. Embedding và test

```bash
cd backend
.venv/bin/python -m scripts.index_templates     # cần GOOGLE_API_KEY; không có thì search chỉ dùng BM25
.venv/bin/python -m pytest -q tests/test_renderer.py tests/test_search.py
```

`test_all_templates_render_their_examples_without_overflow` render ví dụ của mọi template, nên ví dụ bị tràn sẽ làm test đỏ. Nếu thêm template làm thay đổi kết quả các test tìm kiếm theo từ khoá (`test_keyword_search_finds_template_without_diacritics`), xem lại `tags`/`when_to_use` thay vì sửa test.

Muốn thử template trong luồng thật: dùng skill `debug-agent` với `--template <id>`.
