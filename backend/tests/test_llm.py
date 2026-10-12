import pytest

from agent.llm import GeminiLLM, LLMError
from agent.state import MemeIntent

INTENT = MemeIntent(gist="g", tone="t", search_query="q", safe=True)


class Scripted(GeminiLLM):
    """Thay lời gọi mạng bằng kịch bản: model nào ném lỗi gì."""

    def __init__(self, errors: dict[str, Exception], fallback: str | None = "lite"):
        super().__init__("key", "main", fallback, None)
        self.errors = errors
        self.calls: list[str] = []

    def _invoke(self, model, schema, messages, temperature):
        self.calls.append(model)
        if model in self.errors:
            raise self.errors[model]
        return INTENT


def test_overloaded_primary_falls_back():
    llm = Scripted({"main": RuntimeError("503 UNAVAILABLE high demand")})
    assert llm.structured(MemeIntent, "s", "u") == INTENT
    assert llm.calls == ["main", "lite"]


def test_non_retriable_error_does_not_fall_back():
    llm = Scripted({"main": RuntimeError("400 INVALID_ARGUMENT")})
    with pytest.raises(LLMError):
        llm.structured(MemeIntent, "s", "u")
    assert llm.calls == ["main"]


def test_fallback_failure_raises_llm_error():
    llm = Scripted({"main": RuntimeError("429 RESOURCE_EXHAUSTED"), "lite": RuntimeError("503")})
    with pytest.raises(LLMError):
        llm.structured(MemeIntent, "s", "u")


def test_no_fallback_configured():
    llm = Scripted({"main": RuntimeError("503")}, fallback=None)
    with pytest.raises(LLMError):
        llm.structured(MemeIntent, "s", "u")
    assert llm.calls == ["main"]
