import json


def _make(client, headers, topic="Đi làm thứ 2"):
    job_id = client.post("/api/jobs", json={"topic": topic}, headers=headers).json()["job_id"]
    lines = client.post(f"/api/jobs/{job_id}/run").text.splitlines()
    events = [json.loads(line[6:]) for line in lines if line.startswith("data: ")]
    return next(e for e in events if e["type"] == "result")["memes"]


def _auth(h):
    return {"Authorization": h["Authorization"]}


def test_share_rules_and_feed(client, login):
    owner = login(sub="so-owner", email="so-owner@example.com", name="Chủ Bài")
    other = login(sub="so-other", email="so-other@example.com")
    meme = _make(client, _auth(owner))[0]
    assert meme["post_id"] is None

    body = {"meme_id": meme["id"], "caption": "  Ai cũng từng như vầy  "}
    assert client.post("/api/posts", json=body).status_code == 401
    assert client.post("/api/posts", json=body, headers=_auth(other)).status_code == 403
    post = client.post("/api/posts", json=body, headers=_auth(owner)).json()
    assert post["caption"] == "Ai cũng từng như vầy" and post["mine"] is True
    assert post["author"]["display_name"] == "Chủ Bài" and post["meme"]["id"] == meme["id"]
    # đăng lại cùng meme: trả bài cũ, không tạo bài mới
    assert client.post("/api/posts", json=body, headers=_auth(owner)).json()["id"] == post["id"]
    assert client.get(f"/api/memes/{meme['id']}").json()["post_id"] == post["id"]

    feed = client.get("/api/feed").json()["items"]  # khách xem được
    assert feed[0]["id"] == post["id"] and feed[0]["liked"] is False and feed[0]["mine"] is False
    assert any(p["id"] == post["id"] for p in client.get("/api/feed?sort=hot").json()["items"])
    assert (
        client.post("/api/posts", json={"meme_id": meme["id"], "caption": "x" * 501}, headers=_auth(owner)).status_code
        == 400
    )


def test_guest_meme_cannot_be_shared(client, login):
    meme = _make(client, {})[0]
    h = login(sub="so-guest", email="so-guest@example.com")
    assert client.post("/api/posts", json={"meme_id": meme["id"]}, headers=_auth(h)).status_code == 403


def test_like_unlike_is_idempotent(client, login):
    owner = login(sub="lk-owner", email="lk-owner@example.com")
    fan = login(sub="lk-fan", email="lk-fan@example.com")
    post = client.post(
        "/api/posts", json={"meme_id": _make(client, _auth(owner))[0]["id"]}, headers=_auth(owner)
    ).json()

    assert client.post(f"/api/posts/{post['id']}/like").status_code == 401
    assert client.post(f"/api/posts/{post['id']}/like", headers=_auth(fan)).json() == {"liked": True, "like_count": 1}
    assert client.post(f"/api/posts/{post['id']}/like", headers=_auth(fan)).json()["like_count"] == 1
    feed_post = next(p for p in client.get("/api/feed", headers=_auth(fan)).json()["items"] if p["id"] == post["id"])
    assert feed_post["liked"] is True
    assert client.get("/api/me", headers=_auth(owner)).json()["stats"]["likes"] == 1
    assert client.delete(f"/api/posts/{post['id']}/like", headers=_auth(fan)).json() == {
        "liked": False,
        "like_count": 0,
    }
    assert client.delete(f"/api/posts/{post['id']}/like", headers=_auth(fan)).json()["like_count"] == 0


def test_comments_and_permissions(client, login):
    owner = login(sub="cm-owner", email="cm-owner@example.com")
    a = login(sub="cm-a", email="cm-a@example.com", name="Người A")
    b = login(sub="cm-b", email="cm-b@example.com")
    post = client.post(
        "/api/posts", json={"meme_id": _make(client, _auth(owner))[0]["id"]}, headers=_auth(owner)
    ).json()
    url = f"/api/posts/{post['id']}/comments"

    assert client.post(url, json={"body": "hay"}).status_code == 401
    assert client.post(url, json={"body": "   "}, headers=_auth(a)).status_code == 400
    c1 = client.post(url, json={"body": "  Quá   đúng  luôn "}, headers=_auth(a)).json()
    assert c1["body"] == "Quá đúng luôn" and c1["author"]["display_name"] == "Người A"
    c2 = client.post(url, json={"body": "haha"}, headers=_auth(b)).json()

    detail = client.get(f"/api/posts/{post['id']}", headers=_auth(a)).json()
    assert detail["comment_count"] == 2 and [c["id"] for c in detail["comments"]] == [c1["id"], c2["id"]]
    assert [c["can_delete"] for c in detail["comments"]] == [True, False]

    assert client.delete(f"/api/comments/{c2['id']}", headers=_auth(a)).status_code == 403
    assert client.delete(f"/api/comments/{c2['id']}", headers=_auth(owner)).status_code == 204  # chủ bài xoá được
    assert client.delete(f"/api/comments/{c1['id']}", headers=_auth(a)).status_code == 204
    assert client.get(f"/api/posts/{post['id']}").json()["comment_count"] == 0


def test_edit_delete_and_report(client, login):
    owner = login(sub="ed-owner", email="ed-owner@example.com")
    other = login(sub="ed-other", email="ed-other@example.com")
    memes = _make(client, _auth(owner))
    post = client.post("/api/posts", json={"meme_id": memes[0]["id"]}, headers=_auth(owner)).json()
    pid = post["id"]

    assert client.patch(f"/api/posts/{pid}", json={"caption": "x"}, headers=_auth(other)).status_code == 403
    edited = client.patch(f"/api/posts/{pid}", json={"caption": "Caption mới"}, headers=_auth(owner)).json()
    assert edited["caption"] == "Caption mới" and edited["edited"] is True

    client.post(f"/api/posts/{pid}/like", headers=_auth(other))
    client.post(f"/api/posts/{pid}/comments", json={"body": "ok"}, headers=_auth(other))
    assert client.delete(f"/api/posts/{pid}", headers=_auth(other)).status_code == 403
    assert client.delete(f"/api/posts/{pid}", headers=_auth(owner)).status_code == 204
    assert client.get(f"/api/posts/{pid}").status_code == 404
    assert client.get(f"/api/memes/{memes[0]['id']}").json()["post_id"] is None  # chia sẻ lại được

    second = client.post("/api/posts", json={"meme_id": memes[1]["id"]}, headers=_auth(owner)).json()
    for _ in range(3):
        assert client.post(f"/api/posts/{second['id']}/report", json={"reason": "spam"}).status_code == 204
    assert client.get(f"/api/posts/{second['id']}").status_code == 404
    assert all(p["id"] != second["id"] for p in client.get("/api/feed").json()["items"])


def test_deleted_meme_hides_post_and_profile_posts(client, login):
    owner = login(sub="dm-owner", email="dm-owner@example.com")
    meme = _make(client, _auth(owner))[0]
    post = client.post("/api/posts", json={"meme_id": meme["id"]}, headers=_auth(owner)).json()
    username = owner["user"]["username"]
    assert [p["id"] for p in client.get(f"/api/users/{username}/posts").json()["items"]] == [post["id"]]
    client.delete(f"/api/memes/{meme['id']}", headers=_auth(owner))
    assert client.get(f"/api/posts/{post['id']}").status_code == 404
    assert client.get(f"/api/users/{username}/posts").json()["items"] == []


def test_delete_account_cleans_up_social_data(client, login):
    owner = login(sub="da-owner", email="da-owner@example.com")
    leaver = login(sub="da-leaver", email="da-leaver@example.com")
    post = client.post(
        "/api/posts", json={"meme_id": _make(client, _auth(owner))[0]["id"]}, headers=_auth(owner)
    ).json()
    client.post(f"/api/posts/{post['id']}/like", headers=_auth(leaver))
    client.post(f"/api/posts/{post['id']}/comments", json={"body": "bye"}, headers=_auth(leaver))
    leaver_post = client.post(
        "/api/posts", json={"meme_id": _make(client, _auth(leaver))[0]["id"]}, headers=_auth(leaver)
    ).json()

    assert client.delete("/api/me", headers=_auth(leaver)).status_code == 204
    detail = client.get(f"/api/posts/{post['id']}").json()
    assert detail["like_count"] == 0 and detail["comment_count"] == 0 and detail["comments"] == []
    assert client.get(f"/api/posts/{leaver_post['id']}").status_code == 404
