import json

from sqlalchemy import create_engine, inspect


def _sse(response) -> list[dict]:
    return [json.loads(line[6:]) for line in response.text.splitlines() if line.startswith("data: ")]


def _make(client, headers=None, topic="Sếp giao thêm việc"):
    job_id = client.post("/api/jobs", json={"topic": topic}, headers=headers or {}).json()["job_id"]
    events = _sse(client.post(f"/api/jobs/{job_id}/run"))
    return next(e for e in events if e["type"] == "result")["memes"]


def _auth(h: dict) -> dict:
    return {"Authorization": h["Authorization"]}


def test_google_login_creates_user_and_session(client, login):
    h = login(sub="sub-a", email="Minh.Tran@example.com", name="Minh Trần")
    me = client.get("/api/me", headers=_auth(h)).json()
    assert me["username"] == "minhtran"
    assert me["display_name"] == "Minh Trần"
    assert me["email"] == "Minh.Tran@example.com"
    # đăng nhập lại cùng tài khoản Google: không tạo người dùng mới
    again = login(sub="sub-a", email="Minh.Tran@example.com", name="Tên khác")
    assert again["user"]["id"] == me["id"] and again["user"]["display_name"] == "Minh Trần"


def test_username_collision_gets_suffix(client, login):
    a = login(sub="sub-c1", email="hoa@example.com")["user"]["username"]
    b = login(sub="sub-c2", email="hoa@other.com")["user"]["username"]
    assert a == "hoa" and b != a and b.startswith("hoa")


def test_requires_login_and_logout_revokes_token(client, login):
    assert client.get("/api/me").status_code == 401
    assert client.get("/api/me", headers={"Authorization": "Bearer sai"}).status_code == 401
    h = login(sub="sub-logout", email="out@example.com")
    assert client.post("/api/auth/logout", headers=_auth(h)).status_code == 204
    assert client.get("/api/me", headers=_auth(h)).status_code == 401


def test_job_owned_by_user_shows_in_history_and_profile(client, login):
    h = login(sub="sub-owner", email="chu@example.com", name="Chủ Meme")
    memes = _make(client, _auth(h))
    assert memes[0]["owner"]["username"] == "chu"
    history = client.get("/api/me/memes", headers=_auth(h)).json()
    assert {m["id"] for m in memes} <= {m["id"] for m in history["items"]}
    assert history["items"][0]["topic"] == "Sếp giao thêm việc"
    profile = client.get("/api/users/chu").json()
    assert profile["meme_count"] >= 3 and "email" not in profile

    # chuyển hồ sơ sang riêng tư: không xem được hồ sơ, meme không lộ tên chủ
    client.patch("/api/me", json={"profile_public": False}, headers=_auth(h))
    assert client.get("/api/users/chu").status_code == 404
    assert client.get(f"/api/memes/{memes[0]['id']}").json()["owner"] is None


def test_only_owner_can_edit_or_delete(client, login):
    owner = login(sub="sub-o1", email="o1@example.com")
    meme = _make(client, _auth(owner))[0]
    box = meme["boxes"][0]["id"]
    other = login(sub="sub-o2", email="o2@example.com")
    assert client.post(f"/api/memes/{meme['id']}/rerender", json={"captions": {box: "x"}}).status_code == 403
    assert (
        client.post(
            f"/api/memes/{meme['id']}/rerender", json={"captions": {box: "x"}}, headers=_auth(other)
        ).status_code
        == 403
    )
    edited = client.post(f"/api/memes/{meme['id']}/rerender", json={"captions": {box: "y"}}, headers=_auth(owner))
    assert edited.status_code == 200 and edited.json()["owner"]["username"] == owner["user"]["username"]
    assert client.delete(f"/api/memes/{meme['id']}", headers=_auth(other)).status_code == 403
    assert client.delete(f"/api/memes/{meme['id']}", headers=_auth(owner)).status_code == 204
    assert client.get(f"/api/memes/{meme['id']}").json()["code"] == "deleted"


def test_anonymous_memes_stay_editable(client):
    meme = _make(client)[0]
    assert meme["owner"] is None
    box = meme["boxes"][0]["id"]
    assert client.post(f"/api/memes/{meme['id']}/rerender", json={"captions": {box: "ok"}}).status_code == 200


def test_quota_is_per_account_and_lower_for_guests(client, login):
    from app.config import get_settings

    s = get_settings()
    old = s.quota_anon_per_day, s.quota_user_per_day
    try:
        s.quota_anon_per_day, s.quota_user_per_day = 0, 1
        guest = client.post("/api/jobs", json={"topic": "a"})
        assert guest.status_code == 429 and "Đăng nhập" in guest.json()["message"]
        h = login(sub="sub-quota", email="quota@example.com")
        assert client.get("/api/me/quota", headers=_auth(h)).json() == {
            "limit": 1,
            "used": 0,
            "left": 1,
            "signed_in": True,
        }
        assert client.post("/api/jobs", json={"topic": "a"}, headers=_auth(h)).status_code == 200
        assert client.post("/api/jobs", json={"topic": "b"}, headers=_auth(h)).json()["code"] == "quota_exceeded"
    finally:
        s.quota_anon_per_day, s.quota_user_per_day = old


def test_username_validation(client, login):
    h = login(sub="sub-u1", email="u1@example.com")
    login(sub="sub-u2", email="taken@example.com")
    assert client.patch("/api/me", json={"username": "A!"}, headers=_auth(h)).json()["code"] == "invalid_username"
    assert client.patch("/api/me", json={"username": "taken"}, headers=_auth(h)).json()["code"] == "username_taken"
    assert client.patch("/api/me", json={"username": "Moi_Ten"}, headers=_auth(h)).json()["username"] == "moi_ten"


def test_one_vote_per_user_per_pair(client, login):
    from app.db import Job, Meme, Vote, get_sessionmaker

    with get_sessionmaker()() as s:
        for variant in ("agent", "baseline"):
            job = Job(input_type="topic", topic="Cặp riêng cho test vote", status="done", arena=True, variant=variant)
            s.add(job)
            s.flush()
            s.add(
                Meme(
                    job_id=job.id,
                    template_id="pile",
                    boxes=[],
                    captions={},
                    image_key=f"memes/v-{variant}.webp",
                    variant=variant,
                    rank=1,
                )
            )
        s.commit()

    h = login(sub="sub-voter", email="voter@example.com")
    seen = set()
    while True:  # bầu hết các cặp hiện có
        r = client.get("/api/arena/pair", headers=_auth(h))
        if r.status_code == 404:
            assert r.json()["code"] == "all_voted"
            break
        pair = r.json()
        assert pair["pair_token"] not in seen
        seen.add(pair["pair_token"])
        for _ in range(2):  # bấm 2 lần chỉ tính 1 phiếu
            client.post("/api/arena/vote", json={"pair_token": pair["pair_token"], "winner": "a"}, headers=_auth(h))
    with get_sessionmaker()() as s:
        votes = s.query(Vote).filter(Vote.user_id == h["user"]["id"]).count()
    assert votes == len(seen) >= 1
    assert client.get("/api/me", headers=_auth(h)).json()["stats"]["votes"] == votes


def test_delete_account_removes_memes_and_sessions(client, login):
    h = login(sub="sub-del", email="del@example.com")
    meme = _make(client, _auth(h))[0]
    assert client.delete("/api/me", headers=_auth(h)).status_code == 204
    assert client.get("/api/me", headers=_auth(h)).status_code == 401
    assert client.get(f"/api/memes/{meme['id']}").status_code == 410
    # đăng nhập lại bằng cùng Google: tài khoản mới hoàn toàn
    again = login(sub="sub-del", email="del@example.com")
    assert again["user"]["id"] != h["user"]["id"] and again["user"]["stats"]["memes"] == 0


def test_outdated_database_is_reported_clearly(tmp_path):
    """Bảng cũ thiếu cột mới: báo lỗi rõ ràng lúc khởi động thay vì lỗi khó hiểu khi đang chạy."""
    import pytest

    from app.db import SchemaOutdated, init_db

    engine = create_engine(f"sqlite:///{tmp_path}/old.db")
    with engine.begin() as conn:
        conn.exec_driver_sql("CREATE TABLE jobs (id VARCHAR(16) PRIMARY KEY, topic TEXT)")
    with pytest.raises(SchemaOutdated, match="jobs.user_id"):
        init_db(engine)
    assert "users" in inspect(engine).get_table_names()  # bảng còn thiếu vẫn được tạo
