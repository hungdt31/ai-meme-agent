#!/usr/bin/env bash
# Bật backend (8000) + frontend (3000) với database và ảnh TẠM, ghi PID để tắt an toàn bằng dev_down.sh.
# Dùng: dev_up.sh [--real] [--prod] [--dir <thư mục tạm>]
#   --real  dùng Gemini thật theo backend/.env (mặc định: FakeLLM, không tốn quota)
#   --prod  frontend chạy bản build (next build + next start) thay vì next dev
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../.." && pwd)"
REAL=0
PROD=0
DIR="${TMPDIR:-/tmp}/chememe-dev"
while [[ $# -gt 0 ]]; do
  case "$1" in
    --real) REAL=1 ;;
    --prod) PROD=1 ;;
    --dir) DIR="$2"; shift ;;
    *) echo "Tham số lạ: $1" >&2; exit 2 ;;
  esac
  shift
done
mkdir -p "$DIR"

for port in 8000 3000; do
  if (exec 3<>"/dev/tcp/127.0.0.1/$port") 2>/dev/null; then
    echo "Cổng $port đang bận (có thể người dùng đang chạy server của họ). Không bật thêm." >&2
    exit 1
  fi
done

export DATABASE_URL="sqlite:///$DIR/dev.db" LOCAL_STORAGE_DIR="$DIR/storage" STORAGE_BACKEND=local
if [[ $REAL -eq 0 ]]; then export LLM_FAKE=1; fi

cd "$ROOT/backend"
nohup .venv/bin/uvicorn app.main:app --port 8000 >"$DIR/backend.log" 2>&1 &
echo $! >"$DIR/backend.pid"

cd "$ROOT/frontend"
if [[ $PROD -eq 1 ]]; then
  npx next build >"$DIR/build.log" 2>&1 || { echo "next build lỗi, xem $DIR/build.log" >&2; exit 1; }
  nohup npx next start -p 3000 >"$DIR/frontend.log" 2>&1 &
else
  nohup npx next dev -p 3000 >"$DIR/frontend.log" 2>&1 &
fi
echo $! >"$DIR/frontend.pid"

for _ in $(seq 1 60); do
  if curl -sf localhost:8000/api/health >/dev/null && curl -sf -o /dev/null localhost:3000; then
    echo "Backend:  http://localhost:8000  $(curl -s localhost:8000/api/health)"
    echo "Frontend: http://localhost:3000"
    echo "Dữ liệu tạm + log: $DIR"
    exit 0
  fi
  sleep 1
done
echo "Server chưa lên sau 60 s. Xem $DIR/backend.log và $DIR/frontend.log" >&2
exit 1
