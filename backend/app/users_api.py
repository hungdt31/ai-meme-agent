"""Đăng nhập, tài khoản của tôi, lịch sử meme và hồ sơ công khai."""

from datetime import datetime

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy import delete, func, or_, select, update
from sqlalchemy.orm import Session

from app.auth import google
from app.auth import service as auth
from app.auth.deps import bearer_token, optional_user, require_user
from app.auth.service import USERNAME_RE
from app.core.db import get_session
from app.core.errors import ApiError
from app.core.limits import limiter
from app.core.security import client_hash
from app.memes.quota import get_quota
from app.models import AuthSession, Comment, Job, Meme, Post, PostLike, User
from app.service import delete_meme_files, meme_out
from app.social import post_ids, remove_posts

router = APIRouter(prefix="/api")
PAGE_SIZE = 24


def me_out(session: Session, user: User, request: Request) -> dict:
    memes = session.scalar(select(func.count()).select_from(Meme).where(*_owned_final(user.id))) or 0
    posts = session.scalar(select(func.count()).select_from(Post).where(Post.user_id == user.id)) or 0
    likes = session.scalar(select(func.sum(Post.like_count)).where(Post.user_id == user.id)) or 0
    return {
        "id": user.id,
        "username": user.username,
        "display_name": user.display_name,
        "avatar_url": user.avatar_url,
        "email": user.email,  # chỉ trả cho chính chủ
        "profile_public": user.profile_public,
        "created_at": user.created_at.isoformat(),
        "stats": {"memes": memes, "posts": posts, "likes": likes},
        "quota": get_quota(session, user, client_hash(request)).as_dict(),
    }


def _owned_final(user_id: str) -> tuple:
    """Meme kết quả (top 3 của job hoặc bản đã sửa) còn hiển thị của một người."""
    return (
        Meme.user_id == user_id,
        Meme.hidden.is_(False),
        Meme.deleted.is_(False),
        or_(Meme.rank.is_not(None), Meme.parent_id.is_not(None)),
    )


def _page(session: Session, user: User, before: str | None, owner: User | None) -> dict:
    query = select(Meme, Job.topic).join(Job, Job.id == Meme.job_id).where(*_owned_final(user.id))
    if before:
        try:
            query = query.where(Meme.created_at < datetime.fromisoformat(before))
        except ValueError as e:
            raise ApiError(400, "invalid_input", "Tham số before không hợp lệ") from e
    rows = session.execute(query.order_by(Meme.created_at.desc()).limit(PAGE_SIZE + 1)).all()
    posted = post_ids(session, [m.id for m, _ in rows[:PAGE_SIZE]])
    items = [meme_out(m, owner, post_id=posted.get(m.id)) | {"topic": topic} for m, topic in rows[:PAGE_SIZE]]
    return {"items": items, "next_before": items[-1]["created_at"] if len(rows) > PAGE_SIZE else None}


# ---------- đăng nhập ----------


class GoogleLogin(BaseModel):
    credential: str = Field(min_length=20, max_length=4096)


@router.post("/auth/google")
@limiter.limit("30/hour")
def google_login(request: Request, body: GoogleLogin, session: Session = Depends(get_session)):
    claims = google.verify_google_credential(body.credential)
    user, token, expires = auth.login_with_google(session, claims)
    return {"token": token, "expires_at": expires.isoformat(), "user": me_out(session, user, request)}


@router.post("/auth/logout", status_code=204)
def logout(request: Request, session: Session = Depends(get_session)):
    auth.logout(session, bearer_token(request))
    return Response(status_code=204)


# ---------- tài khoản của tôi ----------


@router.get("/me")
def get_me(request: Request, user: User = Depends(require_user), session: Session = Depends(get_session)):
    return me_out(session, user, request)


@router.get("/me/quota")
def my_quota(request: Request, user: User | None = Depends(optional_user), session: Session = Depends(get_session)):
    """Dùng cho cả khách: hiện số lượt còn lại trên form."""
    return get_quota(session, user, client_hash(request)).as_dict() | {"signed_in": user is not None}


class UpdateMe(BaseModel):
    display_name: str | None = Field(default=None, min_length=1, max_length=60)
    username: str | None = None
    profile_public: bool | None = None


@router.patch("/me")
def update_me(
    request: Request, body: UpdateMe, user: User = Depends(require_user), session: Session = Depends(get_session)
):
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
    return me_out(session, user, request)


@router.delete("/me", status_code=204)
def delete_me(user: User = Depends(require_user), session: Session = Depends(get_session)):
    """Xoá tài khoản: xoá meme, ảnh, bài đăng, tim và bình luận; job cũ được gỡ liên kết."""
    for m in session.scalars(select(Meme).where(Meme.user_id == user.id, Meme.deleted.is_(False))):
        m.deleted = True
        delete_meme_files(m)
    session.execute(update(Job).where(Job.user_id == user.id).values(user_id=None))
    # Bài của người này biến mất cùng tim và bình luận; tim/bình luận của họ ở bài người khác cũng xoá và đếm lại
    remove_posts(session, list(session.scalars(select(Post.id).where(Post.user_id == user.id))))
    touched = set(session.scalars(select(PostLike.post_id).where(PostLike.user_id == user.id)))
    touched |= set(session.scalars(select(Comment.post_id).where(Comment.user_id == user.id)))
    session.execute(delete(PostLike).where(PostLike.user_id == user.id))
    session.execute(delete(Comment).where(Comment.user_id == user.id))
    for post in session.scalars(select(Post).where(Post.id.in_(touched))):
        post.like_count = session.scalar(select(func.count()).select_from(PostLike).where(PostLike.post_id == post.id))
        post.comment_count = session.scalar(select(func.count()).select_from(Comment).where(Comment.post_id == post.id))
    session.execute(update(Meme).where(Meme.user_id == user.id).values(user_id=None))
    for row in session.scalars(select(AuthSession).where(AuthSession.user_id == user.id)):
        session.delete(row)
    session.delete(user)
    session.commit()
    return Response(status_code=204)


@router.get("/me/memes")
def my_memes(
    page: int = Query(1, ge=1),
    page_size: int = Query(12, ge=1, le=48),
    user: User = Depends(require_user),
    session: Session = Depends(get_session),
):
    """Phân trang theo số trang (cho trang Meme của tôi)."""
    total = session.scalar(select(func.count()).select_from(Meme).where(*_owned_final(user.id))) or 0
    pages = max(1, -(-total // page_size))
    page = min(page, pages)
    rows = session.execute(
        select(Meme, Job.topic)
        .join(Job, Job.id == Meme.job_id)
        .where(*_owned_final(user.id))
        .order_by(Meme.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    posted = post_ids(session, [m.id for m, _ in rows])
    items = [meme_out(m, user, post_id=posted.get(m.id)) | {"topic": topic} for m, topic in rows]
    return {"items": items, "page": page, "pages": pages, "total": total, "page_size": page_size}


# ---------- hồ sơ công khai ----------


@router.get("/users/{username}")
def public_profile(username: str, before: str | None = None, session: Session = Depends(get_session)):
    user = session.scalar(select(User).where(User.username == username.lower()))
    if user is None or user.is_banned or not user.profile_public:
        raise ApiError(404, "not_found", "Không tìm thấy người dùng")
    count = session.scalar(select(func.count()).select_from(Meme).where(*_owned_final(user.id))) or 0
    return {
        "username": user.username,
        "display_name": user.display_name,
        "avatar_url": user.avatar_url,
        "joined_at": user.created_at.isoformat(),
        "meme_count": count,
        "memes": _page(session, user, before, owner=user),
    }
