"""Lớp gọi LLM. GeminiLLM gọi thật; FakeLLM trả kết quả cố định để chạy test, CI và dev không cần key."""

import base64
import logging
import re
import threading
import time
from functools import lru_cache
from typing import Protocol, TypeVar

from pydantic import BaseModel

from agent.state import (
    BoxText,
    CaptionBatch,
    CaptionOption,
    CritiqueBatch,
    ImageDescription,
    ImageScore,
    MemeIntent,
    TemplateChoice,
)
from app.core.config import get_settings

log = logging.getLogger(__name__)
T = TypeVar("T", bound=BaseModel)


class LLMError(RuntimeError):
    pass


class LLM(Protocol):
    def structured(
        self, schema: type[T], system: str, user: str, images: list[bytes] | None = None, temperature: float = 0.3
    ) -> T: ...


QUOTA_MARKERS = ("429", "RESOURCE_EXHAUSTED")
OVERLOAD_MARKERS = ("503", "UNAVAILABLE", "overloaded", "high demand", "504", "DEADLINE_EXCEEDED", "500", "INTERNAL")
NETWORK_MARKERS = (
    "timed out",
    "timeout",
    "Timeout",
    "Temporary failure in name resolution",
    "Connection",
    "connection",
    "disconnected",
    "SSL",
    "EOF occurred",
    # Tên exception của httpx/httpcore (thông báo có thể không chứa từ khoá nào ở trên)
    "RemoteProtocolError",
    "ConnectError",
    "ReadError",
    "WriteError",
    "NetworkError",
)
UNAVAILABLE_MARKERS = ("404", "NOT_FOUND", "no longer available")

# Thời gian nghỉ (giây) khi Google không nói rõ phải chờ bao lâu
COOLDOWN_PER_MINUTE = 60
COOLDOWN_PER_DAY = 3600
COOLDOWN_OVERLOAD = 30
COOLDOWN_NETWORK = 10
COOLDOWN_UNAVAILABLE = 24 * 3600


def parse_retry_after(message: str) -> float | None:
    """Đọc thời gian chờ Google gợi ý: 'Please retry in 6h59m23.2s' hoặc retryDelay '37s'."""
    m = re.search(r"retry in ((?:\d+h)?(?:\d+m)?(?:[\d.]+s)?)", message)
    if not m or not m.group(1):
        m = re.search(r"retryDelay['\"]?\s*[:=]\s*['\"]([\d.]+)s", message)
        return float(m.group(1)) if m else None
    parts = re.match(r"(?:(\d+)h)?(?:(\d+)m)?(?:([\d.]+)s)?", m.group(1))
    hours, minutes, seconds = (float(x) if x else 0.0 for x in parts.groups())
    return hours * 3600 + minutes * 60 + seconds


def classify_error(message: str) -> tuple[str, float] | None:
    """Trả (lý do, số giây nghỉ) nếu nên chuyển sang model khác, None nếu là lỗi của request (đổi model cũng vô ích)."""
    if any(m in message for m in QUOTA_MARKERS):
        per_day = "PerDay" in message or "per day" in message.lower()
        default = COOLDOWN_PER_DAY if per_day else COOLDOWN_PER_MINUTE
        return ("hết lượt theo ngày" if per_day else "hết lượt"), parse_retry_after(message) or default
    if any(m in message for m in UNAVAILABLE_MARKERS):
        return "key không dùng được model này", COOLDOWN_UNAVAILABLE
    if any(m in message for m in OVERLOAD_MARKERS):
        return "quá tải", COOLDOWN_OVERLOAD
    if any(m in message for m in NETWORK_MARKERS):
        return "lỗi mạng", COOLDOWN_NETWORK
    return None


class GeminiLLM:
    """Gọi Gemini với chuỗi model dự phòng.

    Model báo hết lượt, quá tải hay không khả dụng sẽ được đánh dấu nghỉ trong một khoảng thời gian (theo gợi ý
    retry của Google nếu có); trong lúc đó các lần gọi khác bỏ qua nó. Trạng thái nằm trong bộ nhớ của tiến trình.
    """

    def __init__(
        self,
        api_key: str,
        model: str,
        fallback_models: list[str] | str | None,
        reasoning_effort: str | None,
        clock=time.monotonic,
        timeout_s: float = 35,
    ):
        if isinstance(fallback_models, str):
            fallback_models = [m.strip() for m in fallback_models.split(",")]
        self.api_key = api_key
        self.model = model
        self.models = list(dict.fromkeys([model, *(m for m in fallback_models or [] if m)]))
        self.reasoning_effort = reasoning_effort
        self.clock = clock
        self.timeout_s = timeout_s
        self._cooldown: dict[str, tuple[float, str]] = {}  # model -> (hết nghỉ lúc, lý do)
        self._lock = threading.Lock()
        self._clients: dict[tuple[str, float], object] = {}

    def status(self) -> list[dict]:
        """Trạng thái từng model, dùng cho /api/health."""
        now = self.clock()
        with self._lock:
            out = []
            for m in self.models:
                until, reason = self._cooldown.get(m, (0.0, ""))
                left = max(0, round(until - now))
                out.append({"model": m, "available": left == 0, "retry_in_s": left, "reason": reason if left else None})
            return out

    def _order(self) -> list[str]:
        """Model đang rảnh theo thứ tự ưu tiên; nếu tất cả đang nghỉ, thử model sắp hết nghỉ sớm nhất."""
        now = self.clock()
        with self._lock:
            ready = [m for m in self.models if self._cooldown.get(m, (0.0, ""))[0] <= now]
            if ready:
                return ready
            return [min(self.models, key=lambda m: self._cooldown[m][0])]

    def _rest(self, model: str, seconds: float, reason: str) -> None:
        with self._lock:
            self._cooldown[model] = (self.clock() + seconds, reason)

    def _client(self, model: str, temperature: float):
        from langchain_google_genai import ChatGoogleGenerativeAI

        key = (model, round(temperature, 2))
        if key not in self._clients:
            kwargs = {"reasoning_effort": self.reasoning_effort} if self.reasoning_effort else {}
            self._clients[key] = ChatGoogleGenerativeAI(
                model=model,
                google_api_key=self.api_key,
                temperature=temperature,
                max_retries=0,  # chuỗi dự phòng tự chuyển model, không thử lại cùng model
                timeout=self.timeout_s,
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
        errors: list[str] = []
        for model in self._order():
            try:
                return self._invoke(model, schema, messages, temperature)
            except Exception as e:  # noqa: BLE001
                verdict = classify_error(f"{type(e).__name__}: {e} {type(e.__cause__).__name__ if e.__cause__ else ''}")
                if verdict is None:  # lỗi của chính request: model khác cũng sẽ lỗi
                    raise LLMError(str(e)) from e
                reason, seconds = verdict
                self._rest(model, seconds, reason)
                errors.append(f"{model}: {reason}")
                log.warning("%s %s, nghỉ %ds; thử model tiếp theo", model, reason, seconds)
        raise LLMError("Mọi model Gemini đều đang bận hoặc hết lượt (" + "; ".join(errors) + ")")


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
    return GeminiLLM(
        s.google_api_key,
        s.gemini_model,
        s.gemini_fallback_model,
        s.gemini_reasoning_effort,
        timeout_s=s.gemini_timeout_s,
    )
