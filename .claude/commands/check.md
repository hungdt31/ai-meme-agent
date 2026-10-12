---
description: Chạy toàn bộ kiểm tra giống CI (ruff, pytest, typecheck, build) và báo kết quả
---

Chạy các kiểm tra giống `.github/workflows/ci.yml`, theo thứ tự, mỗi nhóm một lệnh. Dừng lại ở nhóm đầu tiên bị lỗi để báo, không tự sửa trừ khi được yêu cầu.

1. Backend, trong thư mục `backend/`:
   - `.venv/bin/ruff check .`
   - `.venv/bin/ruff format --check .`
   - `.venv/bin/python -m pytest -q`
2. Frontend, trong thư mục `frontend/`:
   - `npm run typecheck`
   - `npm run build`

Test backend luôn chạy FakeLLM nên không tốn quota Gemini. Không khởi động server, không động vào `backend/storage/`, `backend/chememe.db` hay các file `.env`.

Cuối cùng báo bằng tiếng Việt, ngắn gọn: bước nào qua, bước nào lỗi, kèm đoạn lỗi liên quan (tên test hoặc file:dòng). $ARGUMENTS
