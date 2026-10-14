import pytest

from agent.llm import GeminiLLM, LLMError, classify_error, parse_retry_after
from agent.state import MemeIntent

INTENT = MemeIntent(gist="g", tone="t", search_query="q", safe=True)

DAILY_429 = (
    "429 RESOURCE_EXHAUSTED. Quota exceeded for metric: generate_content_free_tier_requests, limit: 20, "
    "quotaId: GenerateRequestsPerDayPerProjectPerModel-FreeTier. Please retry in 6h59m23.25s."
)
MINUTE_429 = (
    "429 RESOURCE_EXHAUSTED. quotaId: GenerateRequestsPerMinutePerProjectPerModel-FreeTier. Please retry in 37s."
)


class Clock:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t


class Scripted(GeminiLLM):
    """Thay lời gọi mạng bằng kịch bản: model nào ném lỗi gì."""

    def __init__(self, errors: dict[str, Exception], fallbacks=("b", "c"), clock=None):
        super().__init__("key", "a", list(fallbacks), None, clock=clock or Clock())
        self.errors = errors
        self.calls: list[str] = []

    def _invoke(self, model, schema, messages, temperature):
        self.calls.append(model)
        if model in self.errors:
            raise self.errors[model]
        return INTENT


def test_parse_retry_after():
    assert parse_retry_after(DAILY_429) == pytest.approx(6 * 3600 + 59 * 60 + 23.25)
    assert parse_retry_after(MINUTE_429) == 37
    assert parse_retry_after("retryDelay': '12s'") == 12
    assert parse_retry_after("không có gợi ý") is None


def test_classify_error():
    assert classify_error(DAILY_429)[0] == "hết lượt theo ngày"
    assert classify_error("503 UNAVAILABLE high demand") == ("quá tải", 30)
    assert classify_error("504 DEADLINE_EXCEEDED")[0] == "quá tải"
    assert classify_error("The read operation timed out")[0] == "lỗi mạng"
    assert classify_error("404 NOT_FOUND. no longer available to new users")[0] == "key không dùng được model này"
    assert classify_error("400 INVALID_ARGUMENT bad schema") is None


def test_falls_through_chain_until_a_model_works():
    llm = Scripted({"a": RuntimeError(DAILY_429), "b": RuntimeError("503 UNAVAILABLE")})
    assert llm.structured(MemeIntent, "s", "u") == INTENT
    assert llm.calls == ["a", "b", "c"]


def test_exhausted_model_is_skipped_until_cooldown_ends():
    clock = Clock()
    llm = Scripted({"a": RuntimeError(MINUTE_429)}, clock=clock)
    llm.structured(MemeIntent, "s", "u")
    llm.calls.clear()
    llm.structured(MemeIntent, "s", "u")
    assert llm.calls == ["b"]  # 'a' đang nghỉ: không tốn một lần gọi thử
    assert llm.status()[0] == {"model": "a", "available": False, "retry_in_s": 37, "reason": "hết lượt"}

    clock.t += 38
    del llm.errors["a"]
    llm.calls.clear()
    llm.structured(MemeIntent, "s", "u")
    assert llm.calls == ["a"]  # hết nghỉ: quay lại model ưu tiên


def test_daily_quota_rests_for_hours():
    clock = Clock()
    llm = Scripted({"a": RuntimeError(DAILY_429)}, clock=clock)
    llm.structured(MemeIntent, "s", "u")
    clock.t += 3600  # một giờ sau vẫn chưa thử lại
    llm.calls.clear()
    llm.structured(MemeIntent, "s", "u")
    assert llm.calls == ["b"]


def test_request_error_does_not_switch_model():
    llm = Scripted({"a": RuntimeError("400 INVALID_ARGUMENT")})
    with pytest.raises(LLMError):
        llm.structured(MemeIntent, "s", "u")
    assert llm.calls == ["a"]
    assert llm.status()[0]["available"]


def test_all_models_down_raises_and_then_tries_soonest():
    clock = Clock()
    llm = Scripted(
        {"a": RuntimeError(DAILY_429), "b": RuntimeError(MINUTE_429), "c": RuntimeError("503 UNAVAILABLE")},
        clock=clock,
    )
    with pytest.raises(LLMError, match="Mọi model"):
        llm.structured(MemeIntent, "s", "u")
    llm.calls.clear()
    with pytest.raises(LLMError):
        llm.structured(MemeIntent, "s", "u")
    assert llm.calls == ["c"]  # đều đang nghỉ: chỉ thử model hết nghỉ sớm nhất (503 nghỉ 30 s)


def test_fallback_list_from_comma_string_without_duplicates():
    llm = GeminiLLM("key", "a", "b, a ,c,,", None)
    assert llm.models == ["a", "b", "c"]


class RemoteProtocolError(Exception):
    """Giống httpx.RemoteProtocolError: thông báo không chứa từ khoá mạng quen thuộc."""


def test_server_disconnect_switches_model():
    llm = Scripted({"a": RemoteProtocolError("Server disconnected without sending a response.")})
    assert llm.structured(MemeIntent, "s", "u") == INTENT
    assert llm.calls == ["a", "b"]
    assert llm.status()[0]["reason"] == "lỗi mạng"
