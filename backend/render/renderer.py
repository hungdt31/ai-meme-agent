"""Đặt chữ lên ảnh bằng Pillow. Code thuần, không gọi LLM, dùng chung cho agent và nút sửa chữ."""

import io
import unicodedata
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps

from render.templates import Box

FONT_DIR = Path(__file__).resolve().parent / "fonts"
FONT_FILES = {"impact": "Anton-Regular.ttf", "caption": "BeVietnamPro-Bold.ttf", "label": "BeVietnamPro-Bold.ttf"}
LINE_SPACING = {"impact": 1.0, "caption": 1.18, "label": 1.1}
MAX_SIDE = 1080
MAX_FONT_RATIO = 0.12  # cỡ chữ lớn nhất = 12% chiều cao ảnh
MIN_FONT_RATIO = {"impact": 0.035, "caption": 0.03, "label": 0.024}  # nhỏ hơn mức này coi như tràn khung


@dataclass
class RenderResult:
    data: bytes
    overflow: bool
    overflow_boxes: list[str]
    width: int
    height: int


@lru_cache(maxsize=256)
def _font(style: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(FONT_DIR / FONT_FILES[style]), size)


def normalize_text(text: str, style: str) -> str:
    """NFC (tránh dấu tiếng Việt tách khỏi chữ), gộp khoảng trắng, giữ xuống dòng chủ động."""
    text = unicodedata.normalize("NFC", text)
    lines = [" ".join(line.split()) for line in text.split("\n")]
    text = "\n".join(line for line in lines if line)
    return text.upper() if style == "impact" else text


def _text_width(text: str, font: ImageFont.FreeTypeFont, stroke: int) -> float:
    return font.getlength(text) + 2 * stroke


def _wrap(text: str, font: ImageFont.FreeTypeFont, max_width: float, stroke: int) -> list[str] | None:
    """Xuống dòng theo từ, giữ dòng chủ động. Trả None nếu có một từ dài hơn cả khung."""
    lines: list[str] = []
    for paragraph in text.split("\n"):
        wrapped = _wrap_paragraph(paragraph, font, max_width, stroke)
        if wrapped is None:
            return None
        lines.extend(wrapped)
    return lines


def _wrap_paragraph(text: str, font: ImageFont.FreeTypeFont, max_width: float, stroke: int) -> list[str] | None:
    lines: list[str] = []
    current = ""
    for word in text.split(" "):
        candidate = f"{current} {word}".strip()
        if _text_width(candidate, font, stroke) <= max_width:
            current = candidate
            continue
        if not current:
            return None
        lines.append(current)
        current = word
        if _text_width(current, font, stroke) > max_width:
            return None
    if current:
        lines.append(current)
    return lines


def _stroke_for(style: str, size: int) -> int:
    return 0 if style == "caption" else max(2, round(size * 0.07))


def _layout(text: str, style: str, box_w: float, box_h: float, max_lines: int, img_h: int):
    """Tìm cỡ chữ lớn nhất vừa khung bằng tìm kiếm nhị phân. Trả (size, lines, fits)."""
    lo = max(10, int(img_h * MIN_FONT_RATIO[style]))
    hi = max(lo, int(min(img_h * MAX_FONT_RATIO, box_h)))
    best = None
    while lo <= hi:
        mid = (lo + hi) // 2
        font = _font(style, mid)
        stroke = _stroke_for(style, mid)
        lines = _wrap(text, font, box_w, stroke)
        ascent, descent = font.getmetrics()
        line_h = (ascent + descent) * LINE_SPACING[style]
        if lines is not None and len(lines) <= max_lines and line_h * len(lines) <= box_h:
            best = (mid, lines)
            lo = mid + 1
        else:
            hi = mid - 1
    if best:
        return best[0], best[1], True
    # Không vừa: vẽ ở cỡ nhỏ nhất, cắt bớt dòng thừa, đánh dấu tràn
    size = max(10, int(img_h * MIN_FONT_RATIO[style]))
    font = _font(style, size)
    lines = _wrap(text, font, box_w, _stroke_for(style, size)) or text.split("\n")
    return size, lines[:max_lines], False


def _draw_box(draw: ImageDraw.ImageDraw, box: Box, text: str, w: int, h: int) -> bool:
    text = normalize_text(text, box.style)
    if not text:
        return True
    bx, by, bw, bh = box.x * w, box.y * h, box.w * w, box.h * h
    size, lines, fits = _layout(text, box.style, bw, bh, box.max_lines, h)
    font = _font(box.style, size)
    stroke = _stroke_for(box.style, size)
    ascent, descent = font.getmetrics()
    line_h = (ascent + descent) * LINE_SPACING[box.style]
    top = by + (bh - line_h * len(lines)) / 2
    fill, stroke_fill = ("#141413", None) if box.style == "caption" else ("#FFFFFF", "#000000")
    for i, line in enumerate(lines):
        draw.text(
            (bx + bw / 2, top + i * line_h),
            line,
            font=font,
            fill=fill,
            anchor="ma",
            stroke_width=stroke,
            stroke_fill=stroke_fill,
        )
    return fits


def _fit_size(img: Image.Image) -> Image.Image:
    scale = MAX_SIDE / max(img.size)
    if scale < 1:
        img = img.resize((round(img.width * scale), round(img.height * scale)), Image.Resampling.LANCZOS)
    return img


def render_meme(base: Image.Image, boxes: list[Box], captions: dict[str, str], watermark: bool = True) -> RenderResult:
    img = _fit_size(base.convert("RGB").copy())
    w, h = img.size
    draw = ImageDraw.Draw(img)
    overflow_boxes = [b.id for b in boxes if not _draw_box(draw, b, captions.get(b.id, ""), w, h)]
    if watermark:
        size = max(11, int(h * 0.022))
        draw.text(
            (w - size * 0.6, h - size * 0.5),
            "easymeme",
            font=_font("label", size),
            fill="#FFFFFF",
            anchor="rd",
            stroke_width=max(1, size // 8),
            stroke_fill="#5E5D59",
        )
    buf = io.BytesIO()
    img.save(buf, format="WEBP", quality=85, method=4)
    return RenderResult(buf.getvalue(), bool(overflow_boxes), overflow_boxes, w, h)


def prepare_upload(data: bytes, max_px: int) -> bytes:
    """Xoay theo EXIF, giới hạn kích thước, lưu lại thành WebP (bỏ toàn bộ EXIF, kể cả GPS)."""
    img = Image.open(io.BytesIO(data))
    img = ImageOps.exif_transpose(img).convert("RGB")
    if max(img.size) > max_px:
        img.thumbnail((max_px, max_px), Image.Resampling.LANCZOS)
    img = _fit_size(img)
    buf = io.BytesIO()
    img.save(buf, format="WEBP", quality=90)
    return buf.getvalue()


def to_jpeg(webp: bytes, quality: int = 85) -> bytes:
    """Bản JPEG cho thẻ og:image: một số ứng dụng chat không hiện ảnh xem trước dạng WebP."""
    buf = io.BytesIO()
    Image.open(io.BytesIO(webp)).convert("RGB").save(buf, format="JPEG", quality=quality, optimize=True)
    return buf.getvalue()
