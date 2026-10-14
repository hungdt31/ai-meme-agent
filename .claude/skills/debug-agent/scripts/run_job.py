"""Chạy một job Easy Meme ngoài server, đo thời gian từng lần gọi LLM và xuất ảnh để xem.

Chạy từ thư mục backend/ (để Settings đọc được backend/.env):
    .venv/bin/python ../.claude/skills/debug-agent/scripts/run_job.py "Sáng thứ 2 đầu tuần" [--effort low] [--model ...] [--fake]

Database và ảnh luôn ghi vào thư mục tạm, không đụng chememe.db hay storage/ thật.
"""

import argparse
import os
import sys
import tempfile
import time
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("topic")
parser.add_argument("--style", choices=["gen_z", "van_phong", "mua_thi", "choi_chu"])
parser.add_argument("--template", help="ép dùng một template id")
parser.add_argument("--effort", choices=["minimal", "low", "medium", "high", "default"], help="ghi đè GEMINI_REASONING_EFFORT")
parser.add_argument("--model", help="ghi đè GEMINI_MODEL")
parser.add_argument("--fake", action="store_true", help="dùng FakeLLM, không tốn quota")
parser.add_argument("--out", help="thư mục xuất kết quả (mặc định: thư mục tạm)")
args = parser.parse_args()

out = Path(args.out or tempfile.mkdtemp(prefix="chememe-debug-"))
out.mkdir(parents=True, exist_ok=True)
# Biến môi trường thắng giá trị trong .env: ép database và ảnh vào thư mục tạm
os.environ["DATABASE_URL"] = f"sqlite:///{out}/debug.db"
os.environ["LOCAL_STORAGE_DIR"] = str(out / "storage")
os.environ["STORAGE_BACKEND"] = "local"
if args.fake:
    os.environ["LLM_FAKE"] = "1"
if args.model:
    os.environ["GEMINI_MODEL"] = args.model
if args.effort:
    os.environ["GEMINI_REASONING_EFFORT"] = "" if args.effort == "default" else args.effort

sys.path.insert(0, str(Path.cwd()))
from PIL import Image  # noqa: E402

from agent.graph import build_graph, initial_state  # noqa: E402
from agent.llm import get_llm  # noqa: E402
from agent.nodes import Deps  # noqa: E402
from app.config import get_settings  # noqa: E402
from app.storage import LocalStorage  # noqa: E402
from rag.search import get_index  # noqa: E402

settings = get_settings()
base_llm = get_llm()
calls: list[tuple[str, float, int]] = []


class Timed:
    def structured(self, schema, system, user, images=None, temperature=0.3):
        t = time.monotonic()
        try:
            return base_llm.structured(schema, system, user, images, temperature)
        finally:
            calls.append((schema.__name__, time.monotonic() - t, len(images or [])))


mode = "FakeLLM" if settings.use_fake_llm else f"{settings.gemini_model} (effort={settings.gemini_reasoning_effort or 'default'}, fallback={settings.gemini_fallback_model or 'none'})"
print(f"LLM: {mode}\nOutput: {out}\n")

storage = LocalStorage(str(out / "storage"), "file://")
deps = Deps(llm=Timed(), index=get_index(), storage=storage, settings=settings)
graph = build_graph(deps)
t0 = time.monotonic()
final = None
for mode_, chunk in graph.stream(
    initial_state("debug", args.topic, args.style, None, args.template), stream_mode=["custom", "values"]
):
    if mode_ == "custom" and chunk["type"] == "node_end":
        print(f"[{time.monotonic() - t0:5.1f}s] {chunk['node']:15} {chunk['summary']}")
    elif mode_ == "values":
        final = chunk
total = time.monotonic() - t0

print("\nLLM calls:")
for name, secs, n_img in calls:
    print(f"  {name:15} {secs:5.1f}s" + (f"  ({n_img} ảnh)" if n_img else ""))
print(f"Tổng: {total:.1f}s, {len(calls)} lần gọi, vòng cuối = {final.get('round')}")

if final.get("refusal") and not final.get("winners"):
    print(f"\nTỪ CHỐI: {final['refusal']}")
    sys.exit(0)

print("\nỨng viên (giữ = ✓):")
for c in final["candidates"]:
    s = c.scores or {}
    mark = "✓" if c.kept else " "
    print(f"  {mark} {c.id:6} {c.template_id or 'upload':20} tràn={c.overflow!s:5} "
          f"đọc={s.get('readable')} hợp={s.get('fit')} hài={s.get('funny')} an_toàn={s.get('safe')} | {c.captions}")
    if c.feedback and not c.kept:
        print(f"           nhận xét: {c.feedback}")

winners = final.get("winners", [])
if winners:
    sheet = Image.new("RGB", (360 * len(winners), 360), "white")
    for i, w in enumerate(winners):
        sheet.paste(Image.open(out / "storage" / w.image_key).convert("RGB").resize((360, 360)), (i * 360, 0))
    sheet_path = out / "winners.png"
    sheet.save(sheet_path)
    print(f"\nTop {len(winners)}: {sheet_path}")
