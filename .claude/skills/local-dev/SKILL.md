---
name: local-dev
description: Bật backend FastAPI và frontend Next.js của ChếMeme trên máy để thử tính năng hoặc kiểm tra thay đổi chạy thật (chế meme qua SSE, trang chia sẻ có og:image, đăng nhập, đấu trường), dùng database và ảnh tạm rồi tắt sạch bằng PID. Dùng khi cần chạy thử app, kiểm tra end-to-end, hay xác nhận một sửa đổi hoạt động ngoài unit test.
argument-hint: "[--real] [--prod]"
---

# Chạy thử ChếMeme trên máy

Hai script bật/tắt server với **database và ảnh tạm**, không bao giờ dùng `backend/chememe.db` hay `backend/storage/` của người dùng.

```bash
.claude/skills/local-dev/scripts/dev_up.sh --dir "$SCRATCH"          # FakeLLM, next dev
.claude/skills/local-dev/scripts/dev_up.sh --dir "$SCRATCH" --prod   # bản build production (phát hiện được lỗi chỉ có khi build)
.claude/skills/local-dev/scripts/dev_up.sh --dir "$SCRATCH" --real   # Gemini thật theo backend/.env (tốn quota)
.claude/skills/local-dev/scripts/dev_down.sh --dir "$SCRATCH" [--clean]
```

`$SCRATCH` là một thư mục nháp (scratchpad của phiên nếu có). Chạy từ thư mục gốc `chememe/`.

- Nếu cổng 8000 hoặc 3000 đang bận, script dừng lại: rất có thể người dùng đang chạy server của họ. Hỏi người dùng thay vì tắt tiến trình đó.
- Luôn tắt bằng `dev_down.sh` (tắt theo PID và tiến trình con). **Không** dùng `pkill -f` trong cùng lệnh có chứa chuỗi khớp, vì nó tắt luôn shell đang chạy.
- `--real` gọi Gemini bằng key của người dùng: chỉ dùng khi họ đồng ý.

## Kiểm tra nhanh sau khi bật

```bash
curl -s localhost:8000/api/health
JOB=$(curl -s -X POST localhost:8000/api/jobs -H 'Content-Type: application/json' \
  -d '{"topic":"Sáng thứ 2 đầu tuần"}' | python3 -c 'import sys,json;print(json.load(sys.stdin)["job_id"])')
curl -sN -X POST localhost:8000/api/jobs/$JOB/run > "$SCRATCH/sse.txt"
grep -o '"type": "[a-z_]*"' "$SCRATCH/sse.txt" | sort | uniq -c    # cần có node_end, candidate, scored, result, done
MEME=$(grep '"type": "result"' "$SCRATCH/sse.txt" | sed 's/^data: //' | python3 -c 'import sys,json;print(json.load(sys.stdin)["memes"][0]["id"])')
curl -s localhost:3000/m/$MEME | grep -o '<meta property="og:image" content="[^"]*"'   # phải trỏ tới file .jpg
```

Trang khác: `/`, `/job/<id>`, `/arena`, `/about`, `/login`, `/me`, `/u/<username>` — kiểm tra mã trả về bằng `curl -s -o /dev/null -w '%{http_code}'`.

## Thử tính năng cần đăng nhập

Không đăng nhập Google thật được bằng curl. Tạo người dùng và phiên thẳng trong database tạm (cùng `DATABASE_URL` với server):

```bash
cd backend && DATABASE_URL="sqlite:///$SCRATCH/dev.db" .venv/bin/python -c "
import hashlib, secrets
from datetime import UTC, datetime, timedelta
from app.db import AuthSession, User, get_sessionmaker
with get_sessionmaker()() as s:
    u = User(google_sub='dev', email='dev@example.com', display_name='Dev', username='dev'); s.add(u); s.flush()
    t = secrets.token_urlsafe(32)
    s.add(AuthSession(token_hash=hashlib.sha256(t.encode()).hexdigest(), user_id=u.id, expires_at=datetime.now(UTC)+timedelta(days=1)))
    s.commit(); print(t)"
```

Gửi token qua header `Authorization: Bearer <token>`.

Đấu trường cần cặp sinh sẵn: xem skill `arena-evals` (với FakeLLM chạy nhanh, không tốn quota).
