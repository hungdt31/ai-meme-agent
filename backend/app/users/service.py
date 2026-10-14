"""Tài khoản: hồ sơ của tôi, danh sách meme, hồ sơ công khai và xoá tài khoản (điều phối các module khác)."""

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import service as auth
from app.auth.models import User
from app.auth.service import USERNAME_RE
from app.community import service as community
from app.core.errors import ApiError
from app.memes import service as memes
from app.memes.quota import get_quota
from app.memes.schemas import meme_out
from app.users.schemas import UpdateMe

PROFILE_PAGE_SIZE = 24


def me_out(session: Session, user: User, client_hash: str) -> dict:
    posts, likes = community.user_stats(session, user.id)
    return {
        "id": user.id,
        "username": user.username,
        "display_name": user.display_name,
        "avatar_url": user.avatar_url,
        "email": user.email,  # chỉ trả cho chính chủ
        "profile_public": user.profile_public,
        "created_at": user.created_at.isoformat(),
        "stats": {"memes": memes.count_owned(session, user.id), "posts": posts, "likes": likes},
        "quota": get_quota(session, user, client_hash).as_dict(),
    }


def update_profile(session: Session, user: User, body: UpdateMe) -> None:
    if body.display_name is not None:
        user.display_name = " ".join(body.display_name.split())
    if body.username is not None and body.username != user.username:
        username = body.username.lower()
        if not USERNAME_RE.match(username):
            raise ApiError(400, "invalid_username", "Tên người dùng gồm 3–20 ký tự: chữ thường, số, dấu gạch dưới")
        if session.scalar(select(User.id).where(User.username == username)):
            raise ApiError(409, "username_taken", "Tên người dùng này đã có người dùng")
        user.username = username
    if body.profile_public is not None:
        user.profile_public = body.profile_public
    session.commit()


def delete_account(session: Session, user: User) -> None:
    """Xoá meme, ảnh, bài đăng, tim và bình luận; job cũ được gỡ liên kết."""
    memes.detach_user(session, user.id)
    community.purge_user(session, user.id)
    auth.end_all_sessions(session, user.id)
    session.delete(user)
    session.commit()


def _memes_out(session: Session, rows: list[tuple], owner: User | None) -> list[dict]:
    posted = community.post_ids(session, [m.id for m, _ in rows])
    return [meme_out(m, owner, post_id=posted.get(m.id)) | {"topic": topic} for m, topic in rows]


def my_memes(session: Session, user: User, page: int, page_size: int) -> dict:
    """Phân trang theo số trang (cho trang Meme của tôi)."""
    total = memes.count_owned(session, user.id)
    pages = max(1, -(-total // page_size))
    page = min(page, pages)
    rows = memes.list_owned(session, user.id, limit=page_size, offset=(page - 1) * page_size)
    items = _memes_out(session, rows, user)
    return {"items": items, "page": page, "pages": pages, "total": total, "page_size": page_size}


def public_profile(session: Session, username: str, before: datetime | None) -> dict:
    user = session.scalar(select(User).where(User.username == username.lower()))
    if user is None or user.is_banned or not user.profile_public:
        raise ApiError(404, "not_found", "Không tìm thấy người dùng")
    rows = memes.list_owned(session, user.id, limit=PROFILE_PAGE_SIZE + 1, before=before)
    items = _memes_out(session, rows[:PROFILE_PAGE_SIZE], user)
    return {
        "username": user.username,
        "display_name": user.display_name,
        "avatar_url": user.avatar_url,
        "joined_at": user.created_at.isoformat(),
        "meme_count": memes.count_owned(session, user.id),
        "memes": {
            "items": items,
            "next_before": items[-1]["created_at"] if len(rows) > PROFILE_PAGE_SIZE else None,
        },
    }
