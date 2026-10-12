#!/usr/bin/env bash
# Tắt các server do dev_up.sh bật, theo PID đã ghi (kèm tiến trình con). Không dùng pkill -f.
# Dùng: dev_down.sh [--dir <thư mục tạm>] [--clean]   (--clean xoá luôn thư mục tạm đó)
set -uo pipefail

DIR="${TMPDIR:-/tmp}/chememe-dev"
CLEAN=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    --dir) DIR="$2"; shift ;;
    --clean) CLEAN=1 ;;
    *) echo "Tham số lạ: $1" >&2; exit 2 ;;
  esac
  shift
done

kill_tree() {
  local pid=$1
  for child in $(ps -o pid= --ppid "$pid" 2>/dev/null); do kill_tree "$child"; done
  kill "$pid" 2>/dev/null
}

for name in backend frontend; do
  f="$DIR/$name.pid"
  if [[ -f "$f" ]]; then
    pid=$(cat "$f")
    if kill -0 "$pid" 2>/dev/null; then kill_tree "$pid" && echo "Đã tắt $name (PID $pid)"; else echo "$name không còn chạy"; fi
    rm -f "$f"
  fi
done

# Chỉ xoá thư mục do dev_up.sh tạo (có dev.db), không bao giờ xoá thư mục khác
if [[ $CLEAN -eq 1 && -f "$DIR/dev.db" ]]; then
  rm -rf "$DIR" && echo "Đã xoá $DIR"
fi
