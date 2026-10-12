---
name: arena-evals
description: Sinh cặp meme agent-vs-baseline cho trang đấu trường (/arena) của ChếMeme và chạy bộ eval (recall chọn template, an toàn, chất lượng/độ trễ), ước tính quota Gemini trước khi chạy và tóm tắt số liệu. Dùng khi đấu trường trống ("chưa có cặp meme nào"), khi cần số liệu eval cho README/CV, hoặc sau khi đổi prompt/template muốn đo lại.
argument-hint: "[seed N | eval templates|safety|quality]"
disable-model-invocation: true
---

# Đấu trường và eval

Cả hai việc đều gọi Gemini bằng key của người dùng (trừ khi bật FakeLLM), nên **báo ước tính quota và hỏi trước khi chạy thật**.

## 1. Xác định database đích

Lệnh seed ghi vào database mà `backend/.env` đang trỏ tới (SQLite local hoặc Neon). Kiểm tra trước, chỉ đọc:

```bash
cd backend && .venv/bin/python ../.claude/skills/arena-evals/scripts/db_target.py
```

Nếu đích là Neon/production mà người dùng chỉ muốn thử, đề nghị seed vào SQLite tạm bằng cách đặt `DATABASE_URL=sqlite:///<thư mục nháp>/arena.db` và `LOCAL_STORAGE_DIR=<thư mục nháp>/storage` trước lệnh.

## 2. Seed đấu trường

```bash
cd backend && .venv/bin/python -m scripts.seed_arena --limit N
```

- Chủ đề lấy từ `evals/topics.jsonl` (40 chủ đề). Chủ đề đã có cặp thì bỏ qua, nên chạy lại với N lớn hơn chỉ sinh thêm.
- Ước tính với Gemini thật: mỗi chủ đề khoảng 6 lần gọi cho agent + 1 cho baseline, khoảng 45 s. Ví dụ N=10 ≈ 70 lần gọi, 7–8 phút → chạy nền (`run_in_background`) và báo khi xong.
- Thử nhanh không tốn quota: thêm `LLM_FAKE=1` (meme vô nghĩa, chỉ để kiểm tra giao diện /arena).
- Ảnh được lưu theo `STORAGE_BACKEND` của `.env`; nếu là `local` thì nằm trong `backend/storage/` — **không xoá thư mục này**.

Xong thì kiểm tra: `curl -s localhost:8000/api/arena/pair` (cần backend đang chạy với cùng database) hoặc chạy lại `db_target.py` để thấy `arena jobs`.

## 3. Chạy eval

```bash
cd backend
.venv/bin/python -m evals.run_eval templates            # recall@3 keyword / vector / hybrid; vector cần đã chạy scripts.index_templates
.venv/bin/python -m evals.run_eval safety               # 20 prompt tấn công + 20 chủ đề vô hại, mỗi cái 1 lần gọi
.venv/bin/python -m evals.run_eval quality --limit 10   # chạy cả graph: ~6 lần gọi/chủ đề
```

Không có key thì script chạy FakeLLM: số liệu chỉ để kiểm tra script, **không được báo như kết quả thật**.

## 4. Báo kết quả

Tóm tắt ngắn bằng tiếng Việt:
- `templates`: recall@3 của từng chế độ; lưu ý thư viện chỉ có vài template nên recall cao là dễ đạt.
- `safety`: số prompt tấn công bị chặn / tổng, liệt kê prompt lọt (`redteam_missed`) và chủ đề vô hại bị chặn nhầm. Mục tiêu trong spec: chặn 100%, chặn nhầm ≤ 5%.
- `quality`: p50/p95 giây, số lần gọi trung bình, tỷ lệ tràn chữ (mục tiêu < 2%, p50 < 20 s trong spec ban đầu).
- Tỷ lệ thắng của agent ở đấu trường: `GET /api/arena/stats`; dưới ~300 phiếu thì nói rõ là chưa đủ tin cậy.

Chỉ ghi số liệu vào README/CV khi chúng đến từ lần chạy thật với Gemini.
