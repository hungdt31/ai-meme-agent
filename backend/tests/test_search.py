from rag.search import BM25, TemplateIndex, fold
from render.templates import load_templates


def test_fold_removes_vietnamese_diacritics():
    assert fold("Đặt báo thức") == "dat bao thuc"


def test_keyword_search_finds_template_without_diacritics():
    index = TemplateIndex(load_templates(), embedder=None, index_path=_missing())
    assert index.search("bi giao them viec qua tai", k=3, mode="keyword")[0] == "pile"
    assert index.search("phân vân giữa hai lựa chọn", k=3, mode="keyword")[0] == "two-buttons"


def test_search_always_returns_k_templates():
    index = TemplateIndex(load_templates(), embedder=None, index_path=_missing())
    assert len(index.search("xyz không khớp gì", k=4)) == 4


class FakeEmbedder:
    """Vector 2 chiều: template 'calm-clock' gần mọi câu hỏi nhất."""

    def embed_documents(self, texts, task_type=None):
        return [[1.0, 0.0] if "Vẫn ổn mà" in t else [0.0, 1.0] for t in texts]

    def embed_query(self, text, task_type=None):
        return [1.0, 0.1]


def test_hybrid_fuses_vector_and_keyword(tmp_path):
    index = TemplateIndex(load_templates(), embedder=FakeEmbedder(), index_path=tmp_path / "idx.json")
    assert index.build() == len(load_templates())
    assert index.build() == 0  # đã có vector, không embed lại
    assert index.search("bất kỳ", k=1, mode="vector") == ["calm-clock"]
    # 'pile' khớp từ khoá và có vector: RRF đưa lên đầu dù vector thuần nghiêng về 'calm-clock'
    assert index.search("giao thêm việc quá tải", k=1, mode="hybrid") == ["pile"]
    assert "calm-clock" in index.search("giao thêm việc quá tải", k=len(load_templates()), mode="hybrid")


def test_bm25_scores_only_matching_docs():
    bm = BM25({"a": "sếp giao việc", "b": "mèo ngủ"})
    assert set(bm.scores("giao việc")) == {"a"}


def _missing():
    from pathlib import Path

    return Path("/nonexistent/index.json")
