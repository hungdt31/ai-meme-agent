from agent.graph import build_graph, initial_state
from agent.llm import FakeLLM
from agent.nodes import Deps
from agent.state import CritiqueBatch, ImageScore
from app.core.config import get_settings
from app.core.storage import LocalStorage
from rag.search import TemplateIndex
from render.templates import load_templates


def _deps(tmp_path, llm=None) -> Deps:
    return Deps(
        llm=llm or FakeLLM(),
        index=TemplateIndex(load_templates(), embedder=None, index_path=tmp_path / "idx.json"),
        storage=LocalStorage(str(tmp_path / "store"), "http://test"),
        settings=get_settings(),
    )


def test_topic_produces_three_memes_from_different_templates(tmp_path):
    state = build_graph(_deps(tmp_path)).invoke(initial_state("j1", "Sếp giao thêm việc chiều thứ 5", None, None, None))
    winners = state["winners"]
    assert len(winners) == 3
    assert len({w.template_id for w in winners}) == 3
    assert all(not w.overflow and w.scores["safe"] == 5 for w in winners)
    assert state["round"] == 0
    # understand + pick + write + critique 12 ảnh chia 2 lô
    assert state["llm_calls"] == 5


def test_unsafe_topic_is_refused_before_any_generation(tmp_path):
    state = build_graph(_deps(tmp_path)).invoke(initial_state("j2", "meme chính trị về một người", None, None, None))
    assert state["refusal"]
    assert state["suggestions"]
    assert not state.get("candidates")


def test_forced_template_skips_search(tmp_path):
    state = build_graph(_deps(tmp_path)).invoke(initial_state("j3", "Ôn thi", None, None, "brain-levels"))
    assert {w.template_id for w in state["winners"]} == {"brain-levels"}


class HarshCritic(FakeLLM):
    """Vòng đầu chê hết, vòng sau cho qua: kiểm tra vòng viết lại."""

    def __init__(self):
        self.critique_calls = 0

    def structured(self, schema, system, user, images=None, temperature=0.3):
        if schema is CritiqueBatch:
            self.critique_calls += 1
            n = len(images or [])
            good = "Vòng trước bị chê" in user or self.critique_calls > 2
            return CritiqueBatch(
                scores=[
                    ImageScore(index=i, readable=5, fit=4 if good else 1, funny=4, safe=5, feedback="nhạt quá")
                    for i in range(n)
                ]
            )
        return super().structured(schema, system, user, images, temperature)


def test_rejected_round_triggers_rewrite_with_feedback(tmp_path):
    critic = HarshCritic()
    state = build_graph(_deps(tmp_path, critic)).invoke(initial_state("j4", "Thứ 2 đầu tuần", None, None, None))
    assert state["round"] == 1
    assert state["winners"]
    assert all(w.round == 1 for w in state["winners"])


def test_upload_flow_uses_image_and_default_layout(tmp_path):
    import io

    from PIL import Image

    deps = _deps(tmp_path)
    buf = io.BytesIO()
    Image.new("RGB", (600, 400), "#88aa55").save(buf, format="WEBP")
    deps.storage.put("uploads/u1.webp", buf.getvalue())
    state = build_graph(deps).invoke(initial_state("j5", "", None, "uploads/u1.webp", None))
    assert state["winners"]
    assert all(w.template_id is None for w in state["winners"])
    assert set(state["winners"][0].captions) == {"top", "bottom"}
