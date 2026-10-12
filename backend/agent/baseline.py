"""Baseline cho đấu trường: Gemini chọn template và viết caption trong MỘT lần gọi, không RAG, không tự chấm.
Dùng chung renderer với agent để so sánh công bằng."""

from agent import prompts
from agent.nodes import Deps
from agent.state import BaselineMeme, Candidate
from render.renderer import render_meme


def run_baseline(job_id: str, topic: str, style: str | None, deps: Deps) -> Candidate:
    blocks = []
    for t in deps.templates.values():
        blocks.append(f"TEMPLATE id={t.id} boxes={','.join(b.id for b in t.boxes)}")
        blocks.append(f"  Tên: {t.name} | Dùng khi: {t.when_to_use}")
        blocks.extend(f"  - {b.id}: tối đa {b.max_chars} ký tự. Vai trò: {b.hint or 'tự do'}" for b in t.boxes)
    user = f"Tình huống: {topic}\nPhong cách: {prompts.STYLES.get(style or '', 'tự do')}\nCác template:\n" + "\n".join(
        blocks
    )
    out = deps.llm.structured(BaselineMeme, prompts.BASELINE, user, temperature=0.9)
    template = deps.templates.get(out.template_id) or next(iter(deps.templates.values()))
    texts = {t.box_id: t.text.replace("\\n", "\n") for t in out.texts}
    captions = {b.id: texts.get(b.id, "") for b in template.boxes}
    result = render_meme(template.load_image(), template.boxes, captions)
    key = f"drafts/{job_id}/baseline.webp"
    deps.storage.put(key, result.data)
    return Candidate(
        id="baseline", round=0, template_id=template.id, captions=captions, image_key=key, overflow=result.overflow
    )
