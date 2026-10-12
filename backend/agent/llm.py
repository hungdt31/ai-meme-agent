"""Lớp gọi LLM. GeminiLLM gọi thật; FakeLLM trả kết quả cố định để chạy test, CI và dev không cần key."""

import base64
import logging
import re
from functools import lru_cache
from typing import Protocol, TypeVar

from pydantic import BaseModel

from agent.state import (
    BaselineMeme,
    BoxText,
    CaptionBatch,
    CaptionOption,
    CritiqueBatch,
    ImageDescription,
    ImageScore,
    MemeIntent,
    TemplateChoice,
)
from app.config import get_settings

log = logging.getLogger(__name__)
T = TypeVar("T", bound=BaseModel)


class LLMError(RuntimeError):
    pass


class LLM(Protocol):
    def structured(
        self, schema: type[T], system: str, user: str, images: list[bytes] | None = None, temperature: float = 0.3
    ) -> T: ...


# Lỗi tạm thời phía Google: model quá tải (503) hoặc hết hạn mức theo phút (429)
RETRIABLE = ("503", "429", "UNAVAILABLE", "RESOURCE_EXHAUSTED", "overloaded", "high demand")


class GeminiLLM:
    def __init__(self, api_key: str, model: str, fallback_model: str | None, reasoning_effort: str | None):
        self.api_key = api_key
        self.model = model
        self.fallback_model = fallback_model if fallback_model and fallback_model != model else None
        self.reasoning_effort = reasoning_effort
        self._clients: dict[tuple[str, float], object] = {}

    def _client(self, model: str, temperature: float):
        from langchain_google_genai import ChatGoogleGenerativeAI

        key = (model, round(temperature, 2))
        if key not in self._clients:
            kwargs = {"reasoning_effort": self.reasoning_effort} if self.reasoning_effort else {}
            self._clients[key] = ChatGoogleGenerativeAI(
                model=model,
                google_api_key=self.api_key,
                temperature=temperature,
                max_retries=1,
                timeout=60,
                **kwargs,
            )
        return self._clients[key]

    def _invoke(self, model: str, schema, messages, temperature: float):
        result = self._client(model, temperature).with_structured_output(schema).invoke(messages)
        if result is None:
            raise LLMError("Gemini trả về rỗng")
        return result

    def structured(self, schema, system, user, images=None, temperature=0.3):
        from langchain_core.messages import HumanMessage, SystemMessage

        content: list[dict] = [{"type": "text", "text": user}]
        for img in images or []:
            data_uri = "data:image/webp;base64," + base64.b64encode(img).decode()
            content.append({"type": "image_url", "image_url": {"url": data_uri}})
        messages = [SystemMessage(content=system), HumanMessage(content=content)]
        try:
            return self._invoke(self.model, schema, messages, temperature)
        except Exception as e:  # noqa: BLE001
            if not self.fallback_model or not any(code in str(e) for code in RETRIABLE):
                raise LLMError(str(e)) from e
            log.warning("%s lỗi tạm thời (%s), chuyển sang %s", self.model, str(e)[:80], self.fallback_model)
        try:
            return self._invoke(self.fallback_model, schema, messages, temperature)
        except Exception as e:  # noqa: BLE001
            raise LLMError(str(e)) from e


class FakeLLM:
    """Giả lập Gemini một cách xác định. Đọc các dòng 'TEMPLATE id=... boxes=...' trong prompt để biết khung chữ."""

    BLOCKLIST = ("chính trị", "khiêu dâm", "giết", "miệt thị", "phân biệt", "tự tử")

    def structured(self, schema, system, user, images=None, temperature=0.3):
        topic = _field(user, "Tình huống") or "Một ngày bình thường"
        if schema is MemeIntent:
            bad = next((w for w in self.BLOCKLIST if w in topic.lower()), None)
            return MemeIntent(
                gist=topic[:120],
                tone="tự giễu",
                search_query=topic[:120],
                safe=bad is None,
                unsafe_reason=f"Chủ đề có nội dung nhạy cảm ({bad})" if bad else None,
            )
        if schema is ImageDescription:
            return ImageDescription(
                scene="Một người đang nhìn vào màn hình",
                mood="mệt mỏi",
                has_faces=False,
                text_layout="top_bottom",
                safe=True,
            )
        if schema is TemplateChoice:
            return TemplateChoice(template_ids=re.findall(r"id=([\w-]+)", user)[:3])
        if schema is CaptionBatch:
            options = []
            for tid, boxes in _templates_in(user):
                for i in range(_int_field(user, "K", 4)):
                    options.append(
                        CaptionOption(
                            template_id=tid,
                            texts=[
                                BoxText(box_id=b, text=_fake_caption(topic, j, i, len(boxes)))
                                for j, b in enumerate(boxes)
                            ],
                        )
                    )
            return CaptionBatch(options=options)
        if schema is CritiqueBatch:
            scores = []
            for i in range(_int_field(user, "N_IMAGES", len(images or []))):
                overflow = f"#{i} overflow=true" in user
                scores.append(
                    ImageScore(
                        index=i,
                        readable=2 if overflow else 5,
                        fit=4,
                        funny=3 + i % 3,
                        safe=5,
                        feedback="Câu quá dài, rút gọn" if overflow else "Ổn",
                    )
                )
            return CritiqueBatch(scores=scores)
        if schema is BaselineMeme:
            tid, boxes = _templates_in(user)[0]
            return BaselineMeme(
                template_id=tid,
                texts=[BoxText(box_id=b, text=_fake_caption(topic, j, 0, len(boxes))) for j, b in enumerate(boxes)],
            )
        raise LLMError(f"FakeLLM chưa hỗ trợ {schema.__name__}")


def _field(text: str, name: str) -> str | None:
    m = re.search(rf"^{name}: (.+)$", text, re.MULTILINE)
    return m.group(1).strip() if m else None


def _int_field(text: str, name: str, default: int) -> int:
    m = re.search(rf"\b{name}=(\d+)", text)
    return int(m.group(1)) if m else default


def _templates_in(text: str) -> list[tuple[str, list[str]]]:
    return [(tid, boxes.split(",")) for tid, boxes in re.findall(r"TEMPLATE id=([\w-]+) boxes=([\w,-]+)", text)]


def _fake_caption(topic: str, box_index: int, variant: int, n_boxes: int) -> str:
    if box_index < n_boxes - 1:
        return topic[:28]
    # Phương án thứ 2 cố tình dài để thử nhánh tràn chữ
    if variant == 1:
        return "Tôi lúc đó " + "rất rất rất " * 12
    return ["Tôi lúc đó", "Ai hiểu cho tôi", "Thôi kệ", "Vẫn ổn mà"][variant % 4]


@lru_cache
def get_llm() -> LLM:
    s = get_settings()
    if s.use_fake_llm:
        log.warning("Không có GOOGLE_API_KEY hoặc LLM_FAKE=1: dùng FakeLLM")
        return FakeLLM()
    return GeminiLLM(s.google_api_key, s.gemini_model, s.gemini_fallback_model, s.gemini_reasoning_effort)
