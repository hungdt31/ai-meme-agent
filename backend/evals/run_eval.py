"""Chạy bộ eval và in kết quả JSON.

python -m evals.run_eval templates            # recall@3: keyword vs vector vs hybrid (vector cần key)
python -m evals.run_eval safety               # tỷ lệ chặn prompt tấn công + tỷ lệ chặn nhầm chủ đề vô hại
python -m evals.run_eval quality --limit 10   # tỷ lệ tràn chữ, số lần gọi LLM, độ trễ
Không có GOOGLE_API_KEY thì chạy bằng FakeLLM: chỉ để kiểm tra script, số liệu không có ý nghĩa.
"""

import argparse
import json
import statistics
import time
from pathlib import Path

from agent.graph import build_graph, default_deps, initial_state
from agent.prompts import UNDERSTAND
from agent.state import MemeIntent

HERE = Path(__file__).resolve().parent


def load(name: str) -> list[dict]:
    return [json.loads(line) for line in (HERE / name).read_text(encoding="utf-8").splitlines() if line.strip()]


def eval_templates(k: int = 3) -> dict:
    index = default_deps().index
    rows = load("template_recall.jsonl")
    out = {}
    for mode in ("keyword", "vector", "hybrid"):
        if mode != "keyword" and not index.vectors:
            out[mode] = "cần GOOGLE_API_KEY và chạy scripts.index_templates"
            continue
        hits = sum(bool(set(index.search(r["topic"], k=k, mode=mode)) & set(r["templates"])) for r in rows)
        out[mode] = round(hits / len(rows), 3)
    return {"recall_at_3": out, "n": len(rows)}


def eval_safety() -> dict:
    llm = default_deps().llm

    def refused(topic: str) -> bool:
        return not llm.structured(MemeIntent, UNDERSTAND, f"Tình huống: {topic}\nPhong cách: tự do").safe

    red, benign = load("redteam.jsonl"), load("benign.jsonl")
    blocked = [r["topic"] for r in red if refused(r["topic"])]
    false_blocks = [r["topic"] for r in benign if refused(r["topic"])]
    return {
        "redteam_blocked": f"{len(blocked)}/{len(red)}",
        "redteam_missed": [r["topic"] for r in red if r["topic"] not in blocked],
        "benign_false_refusal": f"{len(false_blocks)}/{len(benign)}",
        "benign_blocked": false_blocks,
    }


def eval_quality(limit: int) -> dict:
    graph = build_graph(default_deps())
    latencies, calls, returned, overflow = [], [], 0, 0
    for i, row in enumerate(load("topics.jsonl")[:limit]):
        t0 = time.monotonic()
        state = graph.invoke(initial_state(f"eval{i}", row["topic"], None, None, None))
        latencies.append(time.monotonic() - t0)
        calls.append(state.get("llm_calls", 0))
        returned += len(state.get("winners", []))
        overflow += sum(w.overflow for w in state.get("winners", []))
    return {
        "topics": len(latencies),
        "p50_s": round(statistics.median(latencies), 2),
        "p95_s": round(sorted(latencies)[max(0, int(len(latencies) * 0.95) - 1)], 2),
        "avg_llm_calls": round(statistics.mean(calls), 2),
        "memes_returned": returned,
        "overflow_rate": round(overflow / returned, 3) if returned else None,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("suite", choices=["templates", "safety", "quality"])
    parser.add_argument("--limit", type=int, default=10)
    args = parser.parse_args()
    result = {"templates": eval_templates, "safety": eval_safety}.get(args.suite, lambda: eval_quality(args.limit))()
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
