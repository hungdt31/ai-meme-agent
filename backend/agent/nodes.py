"""Các node của graph. Gemini chỉ hiểu, viết và chấm; render và quyết định giữ ảnh nào là code thuần."""

import io
import logging
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Any

from langgraph.config import get_stream_writer
from PIL import Image

from agent import prompts
from agent.llm import LLM
from agent.state import (
    Candidate,
    CaptionBatch,
    CritiqueBatch,
    ImageDescription,
    MemeIntent,
    MemeState,
    TemplateChoice,
)
from app.config import Settings
from app.storage import Storage
from rag.search import TemplateIndex
from render.renderer import render_meme
from render.templates import UPLOAD_LAYOUTS, Box, Template

log = logging.getLogger(__name__)
UPLOAD_ID = "upload"  # id giả cho ảnh người dùng trong prompt
CRITIQUE_BATCH = 6
N_TEMPLATES = 3
N_WINNERS = 3


@dataclass
class Deps:
    llm: LLM
    index: TemplateIndex
    storage: Storage
    settings: Settings

    @property
    def templates(self) -> dict[str, Template]:
        return self.index.templates


def _emit(event: dict[str, Any]) -> None:
    try:
        get_stream_writer()(event)
    except RuntimeError:  # gọi ngoài graph (test node riêng lẻ)
        pass


def _style_text(style: str | None) -> str:
    return prompts.STYLES.get(style or "", "tự do")


class Nodes:
    def __init__(self, deps: Deps):
        self.d = deps

    # ---------- hiểu yêu cầu ----------

    def understand(self, state: MemeState) -> dict:
        _emit({"type": "node_start", "node": "understand"})
        topic = state.get("topic") or "(người dùng không nhập chủ đề, hãy viết dựa trên ảnh)"
        intent = self.d.llm.structured(
            MemeIntent, prompts.UNDERSTAND, f"Tình huống: {topic}\nPhong cách: {_style_text(state.get('style'))}"
        )
        summary = f"Hiểu ý: {intent.gist}" if intent.safe else "Chủ đề không phù hợp"
        _emit({"type": "node_end", "node": "understand", "summary": summary})
        return {"intent": intent, "llm_calls": 1}

    def describe_image(self, state: MemeState) -> dict:
        _emit({"type": "node_start", "node": "describe_image"})
        image = self.d.storage.get(state["upload_key"])
        desc = self.d.llm.structured(ImageDescription, prompts.DESCRIBE_IMAGE, "Mô tả ảnh này.", images=[image])
        update: dict = {"image_desc": desc, "llm_calls": 1}
        if not desc.safe:
            update["refusal"] = desc.unsafe_reason or "Ảnh có nội dung không phù hợp"
        _emit({"type": "node_end", "node": "describe_image", "summary": f"Ảnh: {desc.scene}"})
        return update

    def refuse(self, state: MemeState) -> dict:
        intent = state.get("intent")
        reason = state.get("refusal") or (intent.unsafe_reason if intent else None) or "Chủ đề không phù hợp"
        return {"refusal": reason, "suggestions": prompts.SUGGESTIONS}

    # ---------- chọn template (RAG) ----------

    def pick_templates(self, state: MemeState) -> dict:
        _emit({"type": "node_start", "node": "pick_templates"})
        forced = state.get("forced_template")
        calls = 0
        if forced:
            ids = [forced]
        else:
            intent = state["intent"]
            candidates = self.d.index.search(f"{intent.search_query}. {intent.gist}", k=8)
            listing = "\n".join(
                f"- id={tid} | {self.d.templates[tid].name} | Dùng khi: {self.d.templates[tid].when_to_use}"
                for tid in candidates
            )
            choice = self.d.llm.structured(
                TemplateChoice,
                prompts.PICK_TEMPLATES.format(n=N_TEMPLATES),
                f"Tình huống: {intent.gist}\nGiọng điệu: {intent.tone}\nỨng viên:\n{listing}",
            )
            calls = 1
            ids = [t for t in dict.fromkeys(choice.template_ids) if t in candidates][:N_TEMPLATES]
            ids += [t for t in candidates if t not in ids][: N_TEMPLATES - len(ids)]
        names = ", ".join(self.d.templates[t].name for t in ids)
        _emit({"type": "node_end", "node": "pick_templates", "summary": f"Chọn template: {names}"})
        return {"template_ids": ids, "llm_calls": calls}

    # ---------- viết caption ----------

    def _boxes_for(self, template_id: str | None, state: MemeState) -> list[Box]:
        if template_id is None:
            desc = state.get("image_desc")
            return UPLOAD_LAYOUTS[desc.text_layout if desc else "top_bottom"]
        return self.d.templates[template_id].boxes

    def _template_block(self, template_id: str | None, state: MemeState) -> str:
        boxes = self._boxes_for(template_id, state)
        box_ids = ",".join(b.id for b in boxes)
        lines = []
        if template_id is None:
            desc = state.get("image_desc")
            lines.append(f"TEMPLATE id={UPLOAD_ID} boxes={box_ids}")
            if desc:
                lines.append(f"  Ảnh của người dùng: {desc.scene}; cảm xúc: {desc.mood}")
        else:
            t = self.d.templates[template_id]
            lines.append(f"TEMPLATE id={t.id} boxes={box_ids}")
            lines.append(f"  Tên: {t.name} | Dùng khi: {t.when_to_use}")
            for ex in t.examples[:2]:
                lines.append("  Ví dụ: " + "; ".join(f'{k}="{v}"' for k, v in ex.items()))
        for b in boxes:
            lines.append(f"  - {b.id}: tối đa {b.max_chars} ký tự, {b.max_lines} dòng. Vai trò: {b.hint or 'tự do'}")
        return "\n".join(lines)

    def write_captions(self, state: MemeState) -> dict:
        _emit({"type": "node_start", "node": "write_captions"})
        rnd = state.get("round", 0)
        intent = state["intent"]
        template_ids: list[str | None] = [None] if state.get("upload_key") else list(state["template_ids"])
        k = self.d.settings.captions_per_template if rnd == 0 else max(2, self.d.settings.captions_per_template // 2)
        parts = [
            f"Tình huống: {intent.gist}",
            f"Giọng điệu: {intent.tone}",
            f"Phong cách: {_style_text(state.get('style'))}",
            f"K={k}",
            "Các template:",
            *(self._template_block(t, state) for t in template_ids),
        ]
        rejected = [c.feedback for c in state.get("candidates", []) if c.scores and not c.kept and c.feedback]
        if rejected:
            parts.append("Vòng trước bị chê (hãy sửa):\n" + "\n".join(f"- {f}" for f in dict.fromkeys(rejected)))
        batch = self.d.llm.structured(
            CaptionBatch, prompts.WRITE_CAPTIONS.format(k=k), "\n".join(parts), temperature=0.9
        )

        new: list[Candidate] = []
        per_template: dict[str | None, int] = {}
        max_chars = self.d.settings.max_caption_chars
        for opt in batch.options:
            tid = None if opt.template_id == UPLOAD_ID else opt.template_id
            if tid not in template_ids or per_template.get(tid, 0) >= k:
                continue
            boxes = self._boxes_for(tid, state)
            texts = {t.box_id: t.text.replace("\\n", "\n")[:max_chars] for t in opt.texts}
            captions = {b.id: texts.get(b.id, "") for b in boxes}
            if not any(captions.values()):
                continue
            per_template[tid] = per_template.get(tid, 0) + 1
            new.append(Candidate(id=f"r{rnd}c{len(new)}", round=rnd, template_id=tid, captions=captions))
        _emit({"type": "node_end", "node": "write_captions", "summary": f"Viết {len(new)} caption"})
        return {"candidates": [*state.get("candidates", []), *new], "llm_calls": 1}

    # ---------- render (code) ----------

    def render(self, state: MemeState) -> dict:
        _emit({"type": "node_start", "node": "render"})
        bases: dict[str | None, Image.Image] = {}
        out: list[Candidate] = []
        rendered = overflow = 0
        for c in state["candidates"]:
            if c.image_key:
                out.append(c)
                continue
            if c.template_id not in bases:
                if c.template_id is None:
                    bases[None] = Image.open(io.BytesIO(self.d.storage.get(state["upload_key"])))
                else:
                    bases[c.template_id] = self.d.templates[c.template_id].load_image()
            result = render_meme(bases[c.template_id], self._boxes_for(c.template_id, state), c.captions)
            key = f"drafts/{state['job_id']}/{c.id}.webp"
            self.d.storage.put(key, result.data)
            c = c.model_copy(update={"image_key": key, "overflow": result.overflow})
            rendered += 1
            overflow += result.overflow
            _emit(
                {
                    "type": "candidate",
                    "candidate_id": c.id,
                    "image_url": self.d.storage.url(key),
                    "template_id": c.template_id,
                    "overflow": c.overflow,
                }
            )
            out.append(c)
        _emit({"type": "node_end", "node": "render", "summary": f"Vẽ {rendered} ảnh, {overflow} ảnh tràn chữ"})
        return {"candidates": out}

    # ---------- tự chấm ----------

    def critique(self, state: MemeState) -> dict:
        _emit({"type": "node_start", "node": "critique"})
        todo = [c for c in state["candidates"] if c.scores is None]
        chunks = [todo[i : i + CRITIQUE_BATCH] for i in range(0, len(todo), CRITIQUE_BATCH)]
        gist = state["intent"].gist

        def judge(chunk: list[Candidate]) -> CritiqueBatch:
            lines = [f"Tình huống: {gist}", f"N_IMAGES={len(chunk)}"]
            for i, c in enumerate(chunk):
                caps = "; ".join(f'{k}="{v}"' for k, v in c.captions.items())
                lines.append(
                    f"#{i} template={c.template_id or UPLOAD_ID} overflow={str(c.overflow).lower()} captions={caps}"
                )
            images = [self.d.storage.get(c.image_key) for c in chunk]
            return self.d.llm.structured(
                CritiqueBatch, prompts.CRITIQUE, "\n".join(lines), images=images, temperature=0.1
            )

        # Các lô chấm song song; sự kiện vẫn phát từ luồng chính vì stream writer gắn với context của graph
        with ThreadPoolExecutor(max_workers=max(1, len(chunks))) as pool:
            results = list(pool.map(judge, chunks))

        scored: dict[str, Candidate] = {}
        for chunk, result in zip(chunks, results, strict=True):
            by_index = {s.index: s for s in result.scores}
            for i, c in enumerate(chunk):
                s = by_index.get(i)
                if s is None:  # Gemini bỏ sót ảnh: coi như chưa đạt
                    scores, feedback = {"readable": 1, "fit": 1, "funny": 1, "safe": 1}, "Không chấm được"
                else:
                    scores = {"readable": s.readable, "fit": s.fit, "funny": s.funny, "safe": s.safe}
                    feedback = s.feedback
                scored[c.id] = c.model_copy(update={"scores": scores, "feedback": feedback})
                _emit({"type": "scored", "candidate_id": c.id, "scores": scores, "feedback": feedback})
        candidates = [scored.get(c.id, c) for c in state["candidates"]]
        _emit({"type": "node_end", "node": "critique", "summary": f"Chấm {len(todo)} ảnh"})
        return {"candidates": candidates, "llm_calls": len(chunks)}

    # ---------- chọn kết quả (code) ----------

    def select(self, state: MemeState) -> dict:
        _emit({"type": "node_start", "node": "select"})
        rnd = state.get("round", 0)
        last_round = rnd + 1 >= self.d.settings.max_rounds
        min_readable, min_fit = (3, 2) if last_round else (4, 3)

        def passes(c: Candidate) -> bool:
            s = c.scores or {}
            return (
                not c.overflow
                and s.get("safe", 0) >= 5
                and s.get("readable", 0) >= min_readable
                and s.get("fit", 0) >= min_fit
            )

        kept = sorted((c for c in state["candidates"] if passes(c)), key=lambda c: -c.total())
        winners: list[Candidate] = []
        for c in kept:  # ưu tiên mỗi template một ảnh
            if c.template_id not in {w.template_id for w in winners}:
                winners.append(c)
        winners += [c for c in kept if c not in winners]
        winners = winners[:N_WINNERS]
        kept_ids = {c.id for c in kept}
        candidates = [c.model_copy(update={"kept": c.id in kept_ids}) for c in state["candidates"]]

        update: dict = {"candidates": candidates, "winners": winners}
        if len(winners) >= N_WINNERS or (last_round and winners):
            decision = "done"
        elif not last_round:
            decision, update["round"] = "rewrite", rnd + 1
        else:
            decision = "done"
            update["refusal"] = "Agent chưa tạo được meme đạt chuẩn cho chủ đề này. Thử diễn đạt khác nhé."
            update["suggestions"] = prompts.SUGGESTIONS
        update["decision"] = decision
        summary = f"Giữ {len(kept)}/{len(candidates)} ảnh" + (", viết lại vòng mới" if decision == "rewrite" else "")
        _emit({"type": "node_end", "node": "select", "summary": summary})
        return update
