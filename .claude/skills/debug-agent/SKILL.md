---
name: debug-agent
description: Chạy thử một job chế meme của ChếMeme bên ngoài server để gỡ lỗi agent LangGraph — đo thời gian từng lần gọi Gemini, xem caption, điểm tự chấm, lý do bị loại và ảnh top 3. Dùng khi meme ra nhạt, sai template, bị tràn chữ, job chạy chậm hoặc timeout, Gemini báo lỗi, hay sau khi sửa prompt/node trong backend/agent.
argument-hint: "<chủ đề> [--fake] [--effort low] [--model ...]"
---

# Gỡ lỗi agent bằng một job chạy thử

Script `scripts/run_job.py` dựng graph với chính code trong `backend/`, nhưng **luôn ghi database và ảnh vào thư mục tạm**, không đụng `backend/chememe.db` hay `backend/storage/`.

## Chạy

Luôn chạy từ `backend/` để Settings đọc được `backend/.env` (Claude không đọc được file này, script thì đọc được):

```bash
cd backend
.venv/bin/python ../.claude/skills/debug-agent/scripts/run_job.py "<chủ đề>" --fake      # FakeLLM: kiểm tra luồng, không tốn quota
.venv/bin/python ../.claude/skills/debug-agent/scripts/run_job.py "<chủ đề>"             # Gemini thật theo .env
```

Tuỳ chọn: `--style gen_z|van_phong|mua_thi|choi_chu`, `--template <id>`, `--effort minimal|low|medium|high|default`, `--model <id>`, `--out <thư mục>`.

**Gemini thật tốn quota của người dùng** (khoảng 5–7 lần gọi mỗi job). Chạy `--fake` trước; chỉ chạy thật khi người dùng đồng ý hoặc đang yêu cầu gỡ lỗi chất lượng/tốc độ thật.

## Đọc kết quả

- Dòng `[12.3s] node ...`: tiến độ từng node và tóm tắt.
- `LLM calls`: thời gian mỗi lần gọi. Mốc tham khảo với `gemini-3.8-flash`: effort mặc định ~20–26 s/lần, `low` ~8 s, chấm 6 ảnh ~13 s. Job vượt `JOB_TIMEOUT_S` (120 s) sẽ bị server huỷ.
- `Ứng viên`: mọi caption kèm điểm `readable/fit/funny/safe`, cờ tràn chữ và nhận xét của bước critique. `✓` là ảnh qua bước `select`.
- `winners.png`: ghép top 3 — mở bằng Read để xem ảnh thật.

## Chẩn đoán nhanh

| Triệu chứng | Xem ở đâu |
| --- | --- |
| Chậm / timeout | `LLM calls`; thử `--effort low` hoặc `minimal`; lỗi 503/429 thì xem log có chuyển sang `GEMINI_FALLBACK_MODEL` không |
| Sai template | Bước `pick_templates`; kiểm tra `when_to_use`/`tags` trong `backend/data/templates/*.json` và đã chạy `scripts.index_templates` chưa |
| Tràn chữ nhiều | `max_chars`/kích thước khung của template; renderer trong `backend/render/renderer.py` |
| Bị từ chối nhầm | `MemeIntent.safe` từ bước `understand`; chính sách ở `backend/agent/prompts.py` |
| Toàn ảnh bị loại | Điểm critique so với ngưỡng trong `Nodes.select` (`backend/agent/nodes.py`) |

Sửa prompt trong `nodes.py`/`prompts.py` xong thì chạy lại `--fake` và `pytest`: FakeLLM đọc định dạng prompt (`Tình huống:`, `TEMPLATE id=... boxes=...`, `N_IMAGES=`), đổi định dạng có thể làm hỏng test.
