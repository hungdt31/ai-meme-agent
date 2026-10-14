#!/usr/bin/env bash
# Bật backend + frontend với database và ảnh TẠM, ghi PID để tắt an toàn bằng dev_down.sh.
# Mặc định dùng cổng 8100/3100 để không đụng server 8000/3000 người dùng có thể đang chạy.
# Dùng: dev_up.sh [--real] [--prod] [--dir <thư mục tạm>] [--backend-port N] [--frontend-port N]
#   --real  dùng Gemini thật theo backend/.env (mặc định: FakeLLM, không tốn quota)
#   --prod  frontend chạy bản build (next build + next start) thay vì next dev
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../.." && pwd)"
REAL=0
PROD=0
DIR="${TMPDIR:-/tmp}/chememe-dev"
BP=8100
FP=3100
while [[ $# -gt 0 ]]; do
  case "$1" in
    --real) REAL=1 ;;
    --prod) PROD=1 ;;
    --dir) DIR="$2"; shift ;;
    --backend-port) BP="$2"; shift ;;
    --frontend-port) FP="$2"; shift ;;
    *) echo "Tham số lạ: $1" >&2; exit 2 ;;
  esac
  shift
done
mkdir -p "$DIR"

for port in "$BP" "$FP"; do
  if (exec 3<>"/dev/tcp/127.0.0.1/$port") 2>/dev/null; then
    echo "Cổng $port đang bận (có thể người dùng đang chạy server của họ). Không bật thêm." >&2
    exit 1
  fi
done

export DATABASE_URL="sqlite:///$DIR/dev.db" LOCAL_STORAGE_DIR="$DIR/storage" STORAGE_BACKEND=local
export PUBLIC_BASE_URL="http://localhost:$BP" ALLOWED_ORIGINS="http://localhost:$FP"
export NEXT_PUBLIC_API_URL="http://localhost:$BP" NEXT_PUBLIC_SITE_URL="http://localhost:$FP"
echo "$BP $FP" >"$DIR/ports"
if [[ $REAL -eq 0 ]]; then export LLM_FAKE=1; fi

cd "$ROOT/backend"
nohup .venv/bin/uvicorn app.main:app --port "$BP" >"$DIR/backend.log" 2>&1 &
echo $! >"$DIR/backend.pid"

cd "$ROOT/frontend"
if [[ $PROD -eq 1 ]]; then
  npx next build >"$DIR/build.log" 2>&1 || { echo "next build lỗi, xem $DIR/build.log" >&2; exit 1; }
  nohup npx next start -p "$FP" >"$DIR/frontend.log" 2>&1 &
else
  nohup npx next dev -p "$FP" >"$DIR/frontend.log" 2>&1 &
fi
echo $! >"$DIR/frontend.pid"

for _ in $(seq 1 60); do
  if curl -sf "localhost:$BP/api/health" >/dev/null && curl -sf -o /dev/null "localhost:$FP"; then
    echo "Backend:  http://localhost:$BP  $(curl -s "localhost:$BP/api/health")"
    echo "Frontend: http://localhost:$FP"
    echo "Dữ liệu tạm + log: $DIR"
    exit 0
  fi
  sleep 1
done
echo "Server chưa lên sau 60 s. Xem $DIR/backend.log và $DIR/frontend.log" >&2
exit 1
