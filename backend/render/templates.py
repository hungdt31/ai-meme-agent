"""Thư viện template: mỗi template là một file JSON trong data/templates/ kèm ảnh gốc trong data/templates/images/."""

import json
from functools import lru_cache
from typing import Literal

from PIL import Image
from pydantic import BaseModel, Field

from app.core.config import BACKEND_DIR

TEMPLATE_DIR = BACKEND_DIR / "data" / "templates"
IMAGE_DIR = TEMPLATE_DIR / "images"


class Box(BaseModel):
    id: str
    x: float = Field(ge=0, le=1)
    y: float = Field(ge=0, le=1)
    w: float = Field(gt=0, le=1)
    h: float = Field(gt=0, le=1)
    # impact: chữ trắng viền đen in hoa; caption: chữ đen trên nền sáng; label: chữ trắng viền đen, giữ hoa thường
    style: Literal["impact", "caption", "label"] = "impact"
    max_lines: int = 2
    max_chars: int = 40
    hint: str = ""  # gợi ý cho LLM: khung này nói gì


class Template(BaseModel):
    id: str
    name: str
    image: str
    boxes: list[Box]
    when_to_use: str
    examples: list[dict[str, str]] = []
    tags: list[str] = []
    source: str = ""
    enabled: bool = True

    def load_image(self) -> Image.Image:
        return Image.open(IMAGE_DIR / self.image).convert("RGB")

    def search_text(self) -> str:
        examples = " | ".join(" / ".join(e.values()) for e in self.examples)
        return f"{self.name}. {self.when_to_use}. Từ khoá: {', '.join(self.tags)}. Ví dụ: {examples}"


# Khung chữ mặc định khi tạo meme từ ảnh người dùng tải lên
UPLOAD_LAYOUTS: dict[str, list[Box]] = {
    "top_bottom": [
        Box(id="top", x=0.04, y=0.03, w=0.92, h=0.2, style="impact", max_lines=2, max_chars=40),
        Box(id="bottom", x=0.04, y=0.77, w=0.92, h=0.2, style="impact", max_lines=2, max_chars=40),
    ],
    "top_only": [Box(id="top", x=0.04, y=0.03, w=0.92, h=0.24, style="impact", max_lines=3, max_chars=60)],
    "bottom_only": [Box(id="bottom", x=0.04, y=0.73, w=0.92, h=0.24, style="impact", max_lines=3, max_chars=60)],
}


@lru_cache
def load_templates() -> dict[str, Template]:
    templates: dict[str, Template] = {}
    for path in sorted(TEMPLATE_DIR.glob("*.json")):
        t = Template.model_validate(json.loads(path.read_text(encoding="utf-8")))
        if t.enabled and (IMAGE_DIR / t.image).exists():
            templates[t.id] = t
    return templates


def get_template(template_id: str) -> Template | None:
    return load_templates().get(template_id)
