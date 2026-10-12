"""Kiểm tra một template: JSON hợp lệ, có ảnh, khung chữ nằm đúng chỗ, ví dụ và câu dài tối đa có bị tràn không.

Chạy từ backend/:
    .venv/bin/python ../.claude/skills/add-template/scripts/check_template.py <template_id> [--out <thư mục>]

Xuất <out>/<id>-check.png: ảnh 1 = khung chữ vẽ đè lên ảnh gốc, các ảnh sau = ví dụ đã render, ảnh cuối = mỗi khung
điền câu dài đúng max_chars. Không ghi gì vào backend/.
"""

import argparse
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path.cwd()))
from PIL import Image, ImageDraw  # noqa: E402
from pydantic import ValidationError  # noqa: E402

from render.renderer import _font, render_meme  # noqa: E402
from render.templates import IMAGE_DIR, TEMPLATE_DIR, Template  # noqa: E402

parser = argparse.ArgumentParser()
parser.add_argument("template_id")
parser.add_argument("--out")
args = parser.parse_args()
out = Path(args.out or tempfile.mkdtemp(prefix="chememe-template-"))
out.mkdir(parents=True, exist_ok=True)

path = TEMPLATE_DIR / f"{args.template_id}.json"
if not path.exists():
    sys.exit(f"Không thấy {path}")
try:
    t = Template.model_validate(json.loads(path.read_text(encoding="utf-8")))
except (json.JSONDecodeError, ValidationError) as e:
    sys.exit(f"JSON không hợp lệ:\n{e}")
if t.id != args.template_id:
    sys.exit(f"Trường id ('{t.id}') phải trùng tên file ('{args.template_id}')")
if not (IMAGE_DIR / t.image).exists():
    sys.exit(f"Thiếu ảnh {IMAGE_DIR / t.image}")

problems: list[str] = []
box_ids = [b.id for b in t.boxes]
if len(set(box_ids)) != len(box_ids):
    problems.append("box id bị trùng")
for b in t.boxes:
    if b.x + b.w > 1.001 or b.y + b.h > 1.001:
        problems.append(f"khung '{b.id}' vượt ra ngoài ảnh")
    if not b.hint:
        problems.append(f"khung '{b.id}' thiếu hint (LLM không biết khung này nói gì)")
for i, ex in enumerate(t.examples):
    if set(ex) != set(box_ids):
        problems.append(f"ví dụ #{i} có khung {sorted(ex)} khác khung template {sorted(box_ids)}")
if not t.examples:
    problems.append("chưa có ví dụ: LLM viết kém hơn và search_text nghèo nàn")

base = t.load_image()
print(f"{t.id}: '{t.name}', ảnh {base.size[0]}x{base.size[1]}, {len(t.boxes)} khung")

overlay = base.copy()
draw = ImageDraw.Draw(overlay)
w, h = overlay.size
for b in t.boxes:
    rect = (b.x * w, b.y * h, (b.x + b.w) * w, (b.y + b.h) * h)
    draw.rectangle(rect, outline="#E5484D", width=max(2, w // 240))
    label = f"{b.id} · {b.style} · {b.max_lines} dòng · {b.max_chars} ký tự"
    draw.text((rect[0] + 4, rect[1] + 2), label, font=_font("label", max(14, h // 40)), fill="#FFFFFF",
              stroke_width=2, stroke_fill="#E5484D")
panels = [overlay]

for i, ex in enumerate(t.examples):
    r = render_meme(base, t.boxes, ex)
    print(f"  ví dụ #{i}: " + ("TRÀN " + ", ".join(r.overflow_boxes) if r.overflow else "ok"))
    if r.overflow:
        problems.append(f"ví dụ #{i} tràn ở khung {r.overflow_boxes}")
    panels.append(Image.open(__import__("io").BytesIO(r.data)).convert("RGB"))

# Câu dài đúng max_chars, có dấu chồng (Ố, Ặ) để thử chiều cao dòng
stress = {}
for b in t.boxes:
    words = "Ố ặ ngập việc cuối tuần thứ hai sếp giao thêm deadline gấp".split()
    text = ""
    while len(text) < b.max_chars:
        text = f"{text} {words[len(text) % len(words)]}".strip()
    cut = text[: b.max_chars]
    stress[b.id] = cut.rsplit(" ", 1)[0] if " " in cut and len(text) > b.max_chars else cut
r = render_meme(base, t.boxes, stress)
print("  câu dài tối đa: " + ("TRÀN " + ", ".join(r.overflow_boxes) if r.overflow else "ok"))
if r.overflow:
    problems.append(f"câu dài đúng max_chars bị tràn ở {r.overflow_boxes}: giảm max_chars hoặc nới khung")
panels.append(Image.open(__import__("io").BytesIO(r.data)).convert("RGB"))

size = 360
sheet = Image.new("RGB", (size * len(panels), size), "white")
for i, p in enumerate(panels):
    sheet.paste(p.resize((size, round(size * p.height / p.width)) if p.width >= p.height else (round(size * p.width / p.height), size)), (i * size, 0))
sheet_path = out / f"{t.id}-check.png"
sheet.save(sheet_path)

print(f"\nẢnh kiểm tra: {sheet_path}")
if problems:
    print("Cần sửa:")
    for p in problems:
        print(f"  - {p}")
    sys.exit(1)
print("Không phát hiện vấn đề.")
