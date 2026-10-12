import io
import unicodedata

from PIL import Image

from render.renderer import normalize_text, prepare_upload, render_meme
from render.templates import Box, load_templates


def _render(template_id: str, captions: dict[str, str]):
    t = load_templates()[template_id]
    return render_meme(t.load_image(), t.boxes, captions)


def test_all_templates_render_their_examples_without_overflow():
    for t in load_templates().values():
        for example in t.examples:
            result = render_meme(t.load_image(), t.boxes, example)
            assert not result.overflow, (t.id, result.overflow_boxes)
            img = Image.open(io.BytesIO(result.data))
            assert img.format == "WEBP"
            assert max(img.size) <= 1080


def test_very_long_caption_is_flagged_as_overflow():
    result = _render("calm-clock", {"top": "Thứ 6 " * 40, "bottom": "ok"})
    assert result.overflow
    assert result.overflow_boxes == ["top"]


def test_unbreakable_word_is_flagged_as_overflow():
    result = _render("two-buttons", {"left": "Siêuuuuuuuuuuuuuuuuuuuuuuuudài", "right": "b", "bottom": "c"})
    assert "left" in result.overflow_boxes


def test_normalize_keeps_vietnamese_marks_and_line_breaks():
    decomposed = unicodedata.normalize("NFD", "Chút việc nhỏ:")
    assert normalize_text(f"Sếp nói\n  {decomposed}  ", "caption") == "Sếp nói\nChút việc nhỏ:"
    assert normalize_text("vẫn ổn mà", "impact") == "VẪN ỔN MÀ"


def test_upload_is_resized_and_exif_removed():
    img = Image.new("RGB", (5000, 2500), "red")
    exif = Image.Exif()
    exif[0x010F] = "SecretCamera"  # Make
    buf = io.BytesIO()
    img.save(buf, format="JPEG", exif=exif)
    out = Image.open(io.BytesIO(prepare_upload(buf.getvalue(), max_px=4000)))
    assert max(out.size) <= 1080
    assert not out.getexif()


def test_render_on_uploaded_photo_with_default_layout():
    from render.templates import UPLOAD_LAYOUTS

    photo = Image.new("RGB", (800, 600), "#336699")
    result = render_meme(photo, UPLOAD_LAYOUTS["top_bottom"], {"top": "Khi deploy thứ 6", "bottom": "Và nó chạy"})
    assert not result.overflow
    assert (result.width, result.height) == (800, 600)


def test_missing_caption_box_is_skipped():
    box = Box(id="x", x=0.1, y=0.1, w=0.5, h=0.2)
    result = render_meme(Image.new("RGB", (400, 400)), [box], {})
    assert not result.overflow
