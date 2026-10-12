"""Sinh sẵn cặp meme cho đấu trường: với mỗi chủ đề, 1 meme của agent và 1 meme của baseline.

python -m scripts.seed_arena --limit 20
Tốn quota Gemini: mỗi chủ đề khoảng 6 lần gọi (agent) + 1 lần (baseline).
"""

import argparse
import asyncio
import json

from sqlalchemy import select

from agent.baseline import run_baseline
from agent.graph import default_deps
from app.config import BACKEND_DIR
from app.db import Job, get_sessionmaker, init_db
from app.service import persist_winners, stream_job

TOPICS = BACKEND_DIR / "evals" / "topics.jsonl"


async def seed(limit: int) -> None:
    init_db()
    deps = default_deps()
    topics = [json.loads(line)["topic"] for line in TOPICS.read_text(encoding="utf-8").splitlines() if line.strip()]
    Session = get_sessionmaker()
    for topic in topics[:limit]:
        with Session() as s:
            if s.scalars(select(Job).where(Job.arena.is_(True), Job.topic == topic)).first():
                print("skip", topic)
                continue
            agent_job = Job(input_type="topic", topic=topic, arena=True, variant="agent", status="running")
            s.add(agent_job)
            s.commit()
            agent_id = agent_job.id
        status = None
        async for event in stream_job(agent_id):
            status = event["type"] if event["type"] in ("result", "refused", "error") else status
        with Session() as s:
            job = Job(input_type="topic", topic=topic, arena=True, variant="baseline")
            s.add(job)
            s.flush()
            candidate = run_baseline(job.id, topic, None, deps)
            persist_winners(s, job, [candidate])
            job.status = "done"
            s.commit()
        print(f"{status:8} {topic}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=20)
    asyncio.run(seed(parser.parse_args().limit))


if __name__ == "__main__":
    main()
