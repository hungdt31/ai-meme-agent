import io
import json

from PIL import Image


def _sse(response) -> list[dict]:
    return [json.loads(line[6:]) for line in response.text.splitlines() if line.startswith("data: ")]


def _run(client, **body) -> list[dict]:
    job_id = client.post("/api/jobs", json=body).json()["job_id"]
    return _sse(client.post(f"/api/jobs/{job_id}/run")), job_id


def test_health(client):
    assert client.get("/api/health").json() == {"status": "ok", "fake_llm": True}


def test_full_flow_create_run_get_rerender_report(client):
    events, job_id = _run(client, topic="Deadline thứ 6 mà sếp giao thêm việc", style="van_phong")
    types = [e["type"] for e in events]
    assert types[0] == "node_start" and types[-1] == "done"
    assert "candidate" in types and "scored" in types
    result = next(e for e in events if e["type"] == "result")
    assert len(result["memes"]) == 3
    meme = result["memes"][0]

    # job đã chạy thì không chạy lại được
    assert client.post(f"/api/jobs/{job_id}/run").status_code == 409

    job = client.get(f"/api/jobs/{job_id}").json()
    assert job["status"] == "done" and len(job["memes"]) == 3

    # ảnh public tải được
    assert client.get(meme["image_url"].replace("http://localhost:8000", "")).status_code == 200
    og = client.get(meme["og_image_url"].replace("http://localhost:8000", ""))
    assert og.status_code == 200 and og.content[:3] == b"\xff\xd8\xff"  # JPEG

    got = client.get(f"/api/memes/{meme['id']}").json()
    assert got["topic"] == "Deadline thứ 6 mà sếp giao thêm việc"

    box = got["boxes"][0]["id"]
    new = client.post(f"/api/memes/{meme['id']}/rerender", json={"captions": {box: "Chữ mới"}}).json()
    assert new["parent_id"] == meme["id"] and new["captions"][box] == "Chữ mới" and new["overflow"] is False

    for _ in range(3):
        assert client.post(f"/api/memes/{new['id']}/report", json={"reason": "test"}).status_code == 204
    assert client.get(f"/api/memes/{new['id']}").status_code == 410


def test_unsafe_topic_returns_refused_event(client):
    events, job_id = _run(client, topic="meme miệt thị người khác")
    refused = next(e for e in events if e["type"] == "refused")
    assert refused["suggestions"]
    assert client.get(f"/api/jobs/{job_id}").json()["status"] == "refused"


def test_validation_errors(client):
    assert client.post("/api/jobs", json={}).json()["code"] == "invalid_input"
    assert client.post("/api/jobs", json={"topic": "x" * 301}).status_code == 400
    assert client.post("/api/jobs", json={"topic": "a", "template_id": "khong-co"}).status_code == 400
    assert client.post("/api/jobs/khongco/run").status_code == 404


def test_upload_requires_image_and_consent(client):
    bad = client.post("/api/uploads", files={"file": ("a.txt", b"hello", "text/plain")})
    assert bad.status_code == 415
    buf = io.BytesIO()
    Image.new("RGB", (640, 480), "#aa8844").save(buf, format="PNG")
    upload_id = client.post("/api/uploads", files={"file": ("a.png", buf.getvalue(), "image/png")}).json()["upload_id"]
    assert client.post("/api/jobs", json={"upload_id": upload_id}).status_code == 400  # thiếu consent
    events, _ = _run(client, upload_id=upload_id, consent=True)
    result = next(e for e in events if e["type"] == "result")
    assert result["memes"] and result["memes"][0]["template_id"] is None


def test_arena_pair_vote_and_stats(client):
    from app.db import Job, Meme, get_sessionmaker

    with get_sessionmaker()() as s:
        for variant in ("agent", "baseline"):
            job = Job(input_type="topic", topic="Chủ đề đấu trường", status="done", arena=True, variant=variant)
            s.add(job)
            s.flush()
            s.add(
                Meme(
                    job_id=job.id,
                    template_id="pile",
                    boxes=[],
                    captions={},
                    image_key=f"memes/{variant}.webp",
                    variant=variant,
                    rank=1,
                )
            )
        s.commit()

    pair = client.get("/api/arena/pair").json()
    assert pair["topic"] == "Chủ đề đấu trường"
    winner = "a" if pair["a"]["image_url"].endswith("agent.webp") else "b"
    assert client.post("/api/arena/vote", json={"pair_token": pair["pair_token"], "winner": winner}).status_code == 204
    assert client.post("/api/arena/vote", json={"pair_token": "x.y", "winner": "a"}).status_code == 400
    stats = client.get("/api/arena/stats").json()
    assert stats["votes"] == 1 and stats["agent_win_rate"] == 1.0


def test_templates_list(client):
    items = client.get("/api/templates").json()
    assert {t["id"] for t in items} >= {"pile", "two-buttons"}
