---
name: evals
description: Chạy bộ eval chất lượng của Easy Meme (recall chọn template, an toàn, chất lượng/độ trễ), ước tính quota Gemini trước khi chạy và tóm tắt số liệu. Dùng khi cần số liệu cho README/CV, hoặc sau khi đổi prompt/template muốn đo lại.
argument-hint: "templates|safety|quality"
disable-model-invocation: true
---

# Eval

Các bộ eval gọi Gemini bằng key của người dùng (trừ khi bật FakeLLM), nên **báo ước tính quota và hỏi trước khi chạy thật**.

## 1. Xác định cấu hình

```bash
cd backend && .venv/bin/python ../.claude/skills/evals/scripts/db_target.py
```

Script chỉ đọc. Eval không ghi vào database, nhưng `quality` vẽ ảnh vào storage theo `.env`; muốn tránh thì đặt `LOCAL_STORAGE_DIR=<thư mục nháp>` trước lệnh.

## 2. Chạy

```bash
cd backend
.venv/bin/python -m evals.run_eval templates            # recall@3 keyword / vector / hybrid; vector cần đã chạy scripts.index_templates
.venv/bin/python -m evals.run_eval safety               # 20 prompt tấn công + 20 chủ đề vô hại, mỗi cái 1 lần gọi
.venv/bin/python -m evals.run_eval quality --limit 10   # chạy cả graph: ~5–7 lần gọi/chủ đề → chạy nền khi limit lớn
```

Không có key thì chạy FakeLLM: số liệu chỉ để kiểm tra script, **không được báo như kết quả thật**. Free tier của `gemini-3.8-flash` chỉ khoảng 20 lần gọi/ngày; chuỗi model dự phòng sẽ tự chuyển sang model khác.

## 3. Báo kết quả

Tóm tắt ngắn bằng tiếng Việt:
- `templates`: recall@3 của từng chế độ; thư viện ít template nên recall cao là dễ đạt.
- `safety`: số prompt tấn công bị chặn / tổng, liệt kê prompt lọt và chủ đề vô hại bị chặn nhầm (mục tiêu: chặn 100%, chặn nhầm ≤ 5%).
- `quality`: p50/p95 giây, số lần gọi trung bình, tỷ lệ tràn chữ (mục tiêu < 2%).

Chỉ ghi số liệu vào README/CV khi chúng đến từ lần chạy thật với Gemini.
