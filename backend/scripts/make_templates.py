"""Vẽ bộ template khởi đầu bằng Pillow (hình tự vẽ, không dùng ảnh có bản quyền) và ghi file JSON đi kèm.

Chạy: python -m scripts.make_templates
Thêm template thật: đặt ảnh vào data/templates/images/, viết JSON cùng cấu trúc, rồi chạy scripts.index_templates.
"""

import json

from PIL import Image, ImageDraw

from render.templates import IMAGE_DIR, TEMPLATE_DIR

INK = "#141413"
SKIN = "#F2C9A0"
S = 720


def canvas(color: str) -> tuple[Image.Image, ImageDraw.ImageDraw]:
    img = Image.new("RGB", (S, S), color)
    return img, ImageDraw.Draw(img)


def circle(d: ImageDraw.ImageDraw, cx, cy, r, fill=None, outline=INK, width=5):
    d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=fill, outline=outline, width=width)


def stroke(d: ImageDraw.ImageDraw, pts, width=5, fill=INK):
    d.line(pts, fill=fill, width=width, joint="curve")


def drop(d: ImageDraw.ImageDraw, x, y):
    d.polygon([(x, y), (x + 7, y + 14), (x, y + 20), (x - 7, y + 14)], fill="#5B9BC8")


def pile():
    img, d = canvas("#EFE6D6")
    d.rectangle((0, 0, S, 184), fill="#FFFFFF")
    d.rectangle((0, 600, S, S), fill="#D9C7A8")
    d.rectangle((300, 524, 660, 548), fill="#8B5E3C")
    d.rectangle((320, 548, 336, 608), fill="#6E4A2F")
    d.rectangle((624, 548, 640, 608), fill="#6E4A2F")
    xs = [368, 360, 372, 364, 376, 358, 370, 366, 374, 362, 368, 378, 360, 370, 364, 372, 366]
    for i, x in enumerate(xs):
        y = 506 - 18 * i
        d.rectangle((x, y, x + 224, y + 18), fill="#FFFFFF" if i % 2 == 0 else "#F4F1EA", outline="#BDB6A6", width=2)
    stroke(d, [(180, 456), (180, 552)])
    stroke(d, [(180, 484), (148, 524)])
    stroke(d, [(180, 484), (216, 512)])
    stroke(d, [(180, 552), (156, 612)])
    stroke(d, [(180, 552), (204, 612)])
    circle(d, 180, 428, 28, fill=SKIN)
    circle(d, 170, 424, 3.5, fill=INK, width=1)
    circle(d, 190, 424, 3.5, fill=INK, width=1)
    circle(d, 180, 440, 6, width=3)
    drop(d, 214, 400)
    return img


def two_buttons():
    img, d = canvas("#E9E4D8")
    d.rounded_rectangle((80, 72, 640, 328), radius=32, fill="#CFC8B8", outline=INK, width=5)
    for cx in (240, 480):
        circle(d, cx, 200, 72, fill="#D64545", width=6)
        d.ellipse((cx - 44, 160, cx - 4, 184), fill="#E77B7B")
    d.polygon([(268, 720), (276, 560), (360, 524), (444, 560), (452, 720)], fill="#6B8FB3", outline=INK, width=5)
    circle(d, 360, 444, 60, fill=SKIN)
    stroke(d, [(328, 416), (348, 422)], width=4)
    stroke(d, [(392, 416), (372, 422)], width=4)
    circle(d, 340, 436, 4.5, fill=INK, width=1)
    circle(d, 380, 436, 4.5, fill=INK, width=1)
    stroke(d, [(336, 472), (348, 464), (360, 472), (372, 480), (384, 472)], width=4)
    drop(d, 300, 396)
    drop(d, 432, 388)
    stroke(d, [(432, 600), (458, 530), (452, 484), (440, 462)])
    circle(d, 440, 452, 14, fill=SKIN, width=4)
    return img


def calm_clock():
    img, d = canvas("#DCE5EA")
    d.rectangle((472, 140, 664, 308), fill="#A9C7D8", outline="#FFFFFF", width=10)
    d.line([(568, 140), (568, 308)], fill="#FFFFFF", width=6)
    d.line([(472, 224), (664, 224)], fill="#FFFFFF", width=6)
    circle(d, 192, 232, 68, fill="#FFFFFF", width=6)
    stroke(d, [(192, 232), (196, 272)], width=8)
    stroke(d, [(192, 232), (190, 176)], width=5)
    d.rectangle((0, 552, S, S), fill="#C9D3D9")
    d.rectangle((48, 524, 672, 552), fill="#8B5E3C")
    d.rounded_rectangle((140, 416, 348, 512), radius=8, fill="#3D3D3A")
    d.rounded_rectangle((116, 512, 372, 524), radius=4, fill="#2A2A28")
    d.polygon([(444, 524), (452, 448), (516, 438), (580, 448), (588, 524)], fill="#E39B6B", outline=INK, width=5)
    circle(d, 516, 392, 48, fill=SKIN)
    d.arc((492, 378, 512, 398), 200, 340, fill=INK, width=4)
    d.arc((520, 378, 540, 398), 200, 340, fill=INK, width=4)
    d.arc((498, 396, 534, 424), 20, 160, fill=INK, width=4)
    d.rounded_rectangle((412, 456, 456, 508), radius=6, fill="#FFFFFF", outline=INK, width=4)
    d.arc((444, 464, 476, 496), 270, 90, fill=INK, width=4)
    stroke(d, [(424, 444), (418, 432), (424, 420)], width=3, fill="#6E6D68")
    stroke(d, [(440, 444), (434, 432), (440, 420)], width=3, fill="#6E6D68")
    return img


def no_yes():
    img, d = canvas("#FFFFFF")
    d.rectangle((0, 0, 300, 360), fill="#F4D9A8")
    d.rectangle((0, 360, 300, 720), fill="#F7E4BE")
    d.line([(0, 360), (S, 360)], fill="#D5D1C5", width=4)
    d.line([(300, 0), (300, S)], fill="#D5D1C5", width=4)
    # Trên: quay mặt, giơ tay từ chối
    d.polygon([(70, 360), (80, 260), (150, 240), (220, 260), (230, 360)], fill="#E9A23B", outline=INK, width=5)
    circle(d, 150, 170, 50, fill=SKIN)
    stroke(d, [(124, 170), (144, 166)], width=4)
    stroke(d, [(160, 166), (180, 170)], width=4)
    stroke(d, [(134, 196), (166, 192)], width=4)
    stroke(d, [(200, 290), (236, 196)], width=6)
    circle(d, 240, 180, 24, fill=SKIN, width=4)
    stroke(d, [(250, 296), (286, 332)], width=8, fill="#D64545")
    stroke(d, [(286, 296), (250, 332)], width=8, fill="#D64545")
    # Dưới: cười, chỉ tay đồng ý
    d.polygon([(70, 720), (80, 620), (150, 600), (220, 620), (230, 720)], fill="#E9A23B", outline=INK, width=5)
    circle(d, 150, 530, 50, fill=SKIN)
    circle(d, 134, 522, 4.5, fill=INK, width=1)
    circle(d, 166, 522, 4.5, fill=INK, width=1)
    d.arc((124, 520, 176, 560), 20, 160, fill=INK, width=4)
    stroke(d, [(200, 640), (262, 586)], width=6)
    circle(d, 268, 580, 13, fill=SKIN, width=4)
    stroke(d, [(244, 690), (258, 704), (286, 670)], width=8, fill="#3D8B5A")
    return img


def expectation_reality():
    img, d = canvas("#FFFFFF")
    d.rectangle((0, 140, 356, S), fill="#E4EFE6")
    d.rectangle((364, 140, S, S), fill="#EFE3DF")
    d.line([(360, 0), (360, S)], fill="#D5D1C5", width=8)
    d.ellipse((70, 592, 286, 628), fill="#FFFFFF", outline=INK, width=4)
    d.rectangle((98, 500, 258, 600), fill="#F2B8C6", outline=INK, width=4)
    d.rectangle((118, 420, 238, 500), fill="#F7CBD6", outline=INK, width=4)
    d.rectangle((138, 350, 218, 420), fill="#F2B8C6", outline=INK, width=4)
    circle(d, 178, 334, 14, fill="#D64545", width=3)
    d.ellipse((432, 592, 648, 628), fill="#FFFFFF", outline=INK, width=4)
    d.polygon(
        [(440, 604), (462, 548), (508, 566), (548, 520), (604, 560), (640, 604)], fill="#F2B8C6", outline=INK, width=4
    )
    d.polygon([(500, 560), (520, 500), (560, 512), (548, 540)], fill="#F7CBD6", outline=INK, width=4)
    circle(d, 660, 650, 14, fill="#D64545", width=3)
    return img


def brain_levels():
    img, d = canvas("#FFFFFF")
    colors = ["#E8E6DC", "#E6DCC8", "#F2D3A0", "#F9C65A"]
    for i, color in enumerate(colors):
        top = i * 180
        d.rectangle((440, top, S, top + 180), fill=color)
        cx, cy = 580, top + 96
        if i >= 2:
            n = 8 * (i - 1)
            for k in range(n):
                import math

                a = 2 * math.pi * k / n
                d.line(
                    [
                        (cx + 60 * math.cos(a), cy - 18 + 60 * math.sin(a)),
                        (cx + 84 * math.cos(a), cy - 18 + 84 * math.sin(a)),
                    ],
                    fill="#FFFFFF",
                    width=4,
                )
        circle(d, cx, cy, 52, fill=SKIN)
        circle(d, cx, cy - 18, 14 + 7 * i, fill="#F7A8B8", width=3)
        if i:
            d.line([(0, top), (S, top)], fill="#D5D1C5", width=4)
    d.line([(440, 0), (440, S)], fill="#D5D1C5", width=4)
    return img


TEMPLATES = [
    {
        "id": "pile",
        "name": "Chút việc nhỏ",
        "draw": pile,
        "boxes": [
            {
                "id": "top",
                "x": 0.03,
                "y": 0.015,
                "w": 0.94,
                "h": 0.23,
                "style": "caption",
                "max_lines": 3,
                "max_chars": 70,
                "hint": "câu nói nhẹ nhàng, rồi xuống dòng với 'X thực tế:' để ảnh cho thấy nó khổng lồ",
            }
        ],
        "when_to_use": "Một việc được nói là nhỏ, nhanh, đơn giản nhưng thực tế khổng lồ, ngập đầu; bị giao thêm việc, khối lượng quá tải",
        "examples": [
            {"top": "Sếp: có chút việc nhỏ thôi em\nChút việc nhỏ:"},
            {"top": "Thầy: bài tập về nhà nhẹ thôi\nBài tập:"},
        ],
        "tags": ["quá tải", "giao việc", "ngập việc", "deadline", "nói giảm nói tránh"],
    },
    {
        "id": "two-buttons",
        "name": "Hai nút bấm",
        "draw": two_buttons,
        "boxes": [
            {
                "id": "left",
                "x": 0.236,
                "y": 0.208,
                "w": 0.194,
                "h": 0.14,
                "style": "label",
                "max_lines": 3,
                "max_chars": 24,
                "hint": "lựa chọn 1",
            },
            {
                "id": "right",
                "x": 0.569,
                "y": 0.208,
                "w": 0.194,
                "h": 0.14,
                "style": "label",
                "max_lines": 3,
                "max_chars": 24,
                "hint": "lựa chọn 2",
            },
            {
                "id": "bottom",
                "x": 0.03,
                "y": 0.86,
                "w": 0.94,
                "h": 0.12,
                "style": "impact",
                "max_lines": 2,
                "max_chars": 32,
                "hint": "người đang phân vân",
            },
        ],
        "when_to_use": "Phân vân, khó xử giữa hai lựa chọn đều hấp dẫn hoặc đều tệ, mâu thuẫn bản thân",
        "examples": [{"left": "Ngủ sớm", "right": "Lướt thêm 5 phút", "bottom": "Tôi lúc 1 giờ sáng"}],
        "tags": ["lựa chọn", "phân vân", "khó xử", "mâu thuẫn", "đổ mồ hôi"],
    },
    {
        "id": "calm-clock",
        "name": "Vẫn ổn mà",
        "draw": calm_clock,
        "boxes": [
            {
                "id": "top",
                "x": 0.03,
                "y": 0.02,
                "w": 0.94,
                "h": 0.15,
                "style": "impact",
                "max_lines": 2,
                "max_chars": 36,
                "hint": "hoàn cảnh gấp gáp, giờ giấc",
            },
            {
                "id": "bottom",
                "x": 0.03,
                "y": 0.83,
                "w": 0.94,
                "h": 0.15,
                "style": "impact",
                "max_lines": 2,
                "max_chars": 36,
                "hint": "câu tự trấn an bình thản",
            },
        ],
        "when_to_use": "Bình thản, tự trấn an trong khi tình hình đang rất gấp hoặc sắp toang; sát giờ, nước đến chân",
        "examples": [{"top": "Thứ 6, 17:59", "bottom": "Vẫn kịp, còn 1 phút mà"}],
        "tags": ["bình tĩnh", "sát giờ", "trì hoãn", "sắp toang", "tự an ủi"],
    },
    {
        "id": "no-yes",
        "name": "Không / Có",
        "draw": no_yes,
        "boxes": [
            {
                "id": "no",
                "x": 0.45,
                "y": 0.05,
                "w": 0.51,
                "h": 0.4,
                "style": "caption",
                "max_lines": 4,
                "max_chars": 60,
                "hint": "thứ bị từ chối, chê",
            },
            {
                "id": "yes",
                "x": 0.45,
                "y": 0.55,
                "w": 0.51,
                "h": 0.4,
                "style": "caption",
                "max_lines": 4,
                "max_chars": 60,
                "hint": "thứ được thích, chọn",
            },
        ],
        "when_to_use": "So sánh thứ mình né tránh với thứ mình thích hơn; sở thích trái khoáy, chọn cái kém hợp lý",
        "examples": [{"no": "Ôn bài từ đầu kỳ", "yes": "Học xuyên đêm trước hôm thi"}],
        "tags": ["so sánh", "thích", "không thích", "sở thích", "chọn"],
    },
    {
        "id": "expectation-reality",
        "name": "Kỳ vọng / Thực tế",
        "draw": expectation_reality,
        "boxes": [
            {
                "id": "left",
                "x": 0.02,
                "y": 0.02,
                "w": 0.46,
                "h": 0.16,
                "style": "caption",
                "max_lines": 2,
                "max_chars": 30,
                "hint": "kỳ vọng",
            },
            {
                "id": "right",
                "x": 0.52,
                "y": 0.02,
                "w": 0.46,
                "h": 0.16,
                "style": "caption",
                "max_lines": 2,
                "max_chars": 30,
                "hint": "thực tế",
            },
        ],
        "when_to_use": "Kỳ vọng đẹp đẽ khác xa thực tế phũ phàng; kế hoạch so với kết quả, quảng cáo so với hàng thật",
        "examples": [{"left": "Kế hoạch học cả tuần", "right": "Tối chủ nhật thực tế"}],
        "tags": ["kỳ vọng", "thực tế", "thất vọng", "kế hoạch", "trước sau"],
    },
    {
        "id": "brain-levels",
        "name": "Bốn cấp độ não",
        "draw": brain_levels,
        "boxes": [
            {
                "id": f"l{i + 1}",
                "x": 0.03,
                "y": round(i * 0.25 + 0.025, 3),
                "w": 0.56,
                "h": 0.2,
                "style": "caption",
                "max_lines": 3,
                "max_chars": 50,
                "hint": f"cách làm cấp {i + 1}, càng về sau càng 'cao siêu' một cách vô lý",
            }
            for i in range(4)
        ],
        "when_to_use": "Liệt kê các cách làm từ bình thường đến 'cao siêu' một cách hài hước, leo thang mức độ, càng lúc càng vô lý",
        "examples": [{"l1": "Đặt báo thức", "l2": "Đặt 5 báo thức", "l3": "Nhờ mẹ gọi dậy", "l4": "Không ngủ luôn"}],
        "tags": ["leo thang", "cấp độ", "khai sáng", "so sánh nhiều", "cách giải quyết"],
    },
]


def main():
    IMAGE_DIR.mkdir(parents=True, exist_ok=True)
    for spec in TEMPLATES:
        spec = dict(spec)
        draw = spec.pop("draw")
        image_name = f"{spec['id']}.png"
        draw().save(IMAGE_DIR / image_name, optimize=True)
        spec |= {"image": image_name, "source": "Tự vẽ bằng scripts/make_templates.py", "enabled": True}
        (TEMPLATE_DIR / f"{spec['id']}.json").write_text(
            json.dumps(spec, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        print("wrote", spec["id"])


if __name__ == "__main__":
    main()
