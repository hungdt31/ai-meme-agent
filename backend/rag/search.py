"""Tìm template theo ý nghĩa tình huống: hybrid search (vector + BM25) gộp bằng Reciprocal Rank Fusion.

Vector lưu trong file JSON cạnh template (data/template_index.json) thay vì pgvector: thư viện chỉ vài chục
đến vài trăm template, tính cosine trong bộ nhớ mất dưới 1 ms. Khi vượt vài nghìn template mới cần pgvector.
"""

import hashlib
import json
import logging
import math
import re
import unicodedata
from collections import Counter
from functools import lru_cache
from pathlib import Path

from app.core.config import BACKEND_DIR, get_settings
from render.templates import Template, load_templates

log = logging.getLogger(__name__)
INDEX_PATH = BACKEND_DIR / "data" / "template_index.json"
RRF_K = 60


def fold(text: str) -> str:
    """Bỏ dấu tiếng Việt để tìm theo từ khoá không phụ thuộc cách gõ."""
    text = unicodedata.normalize("NFD", text.lower()).replace("đ", "d")
    return "".join(c for c in text if unicodedata.category(c) != "Mn")


def tokenize(text: str) -> list[str]:
    return re.findall(r"\w+", fold(text))


class BM25:
    def __init__(self, docs: dict[str, str], k1: float = 1.5, b: float = 0.75):
        self.k1, self.b = k1, b
        self.tokens = {doc_id: tokenize(text) for doc_id, text in docs.items()}
        self.avg_len = sum(len(t) for t in self.tokens.values()) / max(1, len(self.tokens))
        df = Counter(term for toks in self.tokens.values() for term in set(toks))
        n = len(self.tokens)
        self.idf = {term: math.log(1 + (n - f + 0.5) / (f + 0.5)) for term, f in df.items()}

    def scores(self, query: str) -> dict[str, float]:
        q = tokenize(query)
        out: dict[str, float] = {}
        for doc_id, toks in self.tokens.items():
            tf = Counter(toks)
            norm = self.k1 * (1 - self.b + self.b * len(toks) / self.avg_len)
            score = sum(self.idf.get(t, 0) * tf[t] * (self.k1 + 1) / (tf[t] + norm) for t in q if t in tf)
            if score > 0:
                out[doc_id] = score
        return out


def cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    return dot / (na * nb) if na and nb else 0.0


def _ranks(scores: dict[str, float]) -> dict[str, int]:
    return {doc_id: i for i, (doc_id, _) in enumerate(sorted(scores.items(), key=lambda kv: -kv[1]))}


class TemplateIndex:
    def __init__(self, templates: dict[str, Template], embedder=None, index_path: Path = INDEX_PATH):
        self.templates = templates
        self.embedder = embedder
        self.index_path = index_path
        self.texts = {tid: t.search_text() for tid, t in templates.items()}
        self.bm25 = BM25(self.texts)
        self.vectors = self._load_vectors()

    def _load_vectors(self) -> dict[str, list[float]]:
        if not self.index_path.exists():
            return {}
        data = json.loads(self.index_path.read_text())
        # Bỏ vector cũ khi mô tả template đã đổi
        return {
            tid: row["vector"]
            for tid, row in data.get("templates", {}).items()
            if tid in self.texts and row.get("hash") == _hash(self.texts[tid])
        }

    def build(self) -> int:
        """Embed các template chưa có vector. Trả số template vừa embed."""
        if self.embedder is None:
            raise RuntimeError("Cần GOOGLE_API_KEY để tạo embedding")
        missing = [tid for tid in self.texts if tid not in self.vectors]
        if missing:
            vectors = self.embedder.embed_documents([self.texts[t] for t in missing], task_type="RETRIEVAL_DOCUMENT")
            self.vectors.update(dict(zip(missing, vectors, strict=True)))
        payload = {
            "model": get_settings().gemini_embed_model,
            "templates": {tid: {"hash": _hash(self.texts[tid]), "vector": v} for tid, v in self.vectors.items()},
        }
        self.index_path.write_text(json.dumps(payload))
        return len(missing)

    def vector_scores(self, query: str) -> dict[str, float]:
        if not self.embedder or not self.vectors:
            return {}
        try:
            q = self.embedder.embed_query(query, task_type="RETRIEVAL_QUERY")
        except Exception:  # noqa: BLE001 - mất embedding thì vẫn còn BM25
            log.exception("embed_query failed, falling back to BM25 only")
            return {}
        return {tid: cosine(q, v) for tid, v in self.vectors.items()}

    def search(self, query: str, k: int = 8, mode: str = "hybrid") -> list[str]:
        """mode: hybrid | vector | keyword (dùng cho eval so sánh)."""
        fused: dict[str, float] = {}
        sources = []
        if mode in ("hybrid", "vector"):
            sources.append(_ranks(self.vector_scores(query)))
        if mode in ("hybrid", "keyword"):
            sources.append(_ranks(self.bm25.scores(query)))
        for ranks in sources:
            for tid, rank in ranks.items():
                fused[tid] = fused.get(tid, 0) + 1 / (RRF_K + rank + 1)
        ordered = sorted(fused, key=lambda t: -fused[t])
        # Template không khớp gì vẫn được xếp cuối để agent luôn có lựa chọn
        ordered += [tid for tid in self.templates if tid not in fused]
        return ordered[:k]


def _hash(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()[:16]


@lru_cache
def get_index() -> TemplateIndex:
    s = get_settings()
    embedder = None
    if not s.use_fake_llm:
        from langchain_google_genai import GoogleGenerativeAIEmbeddings

        embedder = GoogleGenerativeAIEmbeddings(model=s.gemini_embed_model, google_api_key=s.google_api_key)
    return TemplateIndex(load_templates(), embedder)
