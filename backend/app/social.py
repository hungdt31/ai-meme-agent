"""Cộng đồng kiểu Threads: đăng meme của mình kèm caption, bảng tin, thả tim, bình luận."""

import math
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, Request
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy import delete, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth.deps import optional_user, require_user
from app.core.config import get_settings
from app.core.db import get_session
from app.core.errors import ApiError
from app.core.limits import limiter
from app.core.storage import get_storage
from app.models import Comment, Meme, Post, PostLike, User

router = APIRouter(prefix="/api")
PAGE_SIZE = 20
HOT_WINDOW_DAYS = 7
MAX_CAPTION = 500
MAX_COMMENT = 500


def _aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)  # SQLite trả datetime không múi giờ


def author_out(user: User | None) -> dict:
    """Đăng bài là hành động công khai nên luôn hiện tên; chỉ có link hồ sơ khi hồ sơ để công khai."""
    if user is None:
        return {"username": None, "display_name": "Tài khoản đã xoá", "avatar_url": None, "profile_public": False}
    return {
        "username": user.username,
        "display_name": user.display_name,
        "avatar_url": user.avatar_url,
        "profile_public": user.profile_public,
    }


def post_ids(session: Session, meme_ids: list[str]) -> dict[str, str]:
    """meme_id -> post_id cho các meme đã được chia sẻ lên cộng đồng."""
    if not meme_ids:
        return {}
    rows = session.execute(select(Post.meme_id, Post.id).where(Post.meme_id.in_(meme_ids), Post.hidden.is_(False)))
    return dict(rows.all())


def _visible(query):
    return query.join(Meme, Meme.id == Post.meme_id).where(
        Post.hidden.is_(False), Meme.hidden.is_(False), Meme.deleted.is_(False)
    )


def posts_out(session: Session, rows: list[tuple[Post, Meme]], viewer: User | None) -> list[dict]:
    if not rows:
        return []
    users = {u.id: u for u in session.scalars(select(User).where(User.id.in_({p.user_id for p, _ in rows})))}
    liked: set[str] = set()
    if viewer:
        liked = set(
            session.scalars(
                select(PostLike.post_id).where(
                    PostLike.user_id == viewer.id, PostLike.post_id.in_([p.id for p, _ in rows])
                )
            )
        )
    url = get_storage().url
    return [
        {
            "id": p.id,
            "created_at": _aware(p.created_at).isoformat(),
            "edited": p.edited_at is not None,
            "caption": p.caption,
            "author": author_out(users.get(p.user_id)),
            "meme": {"id": m.id, "image_url": url(m.image_key), "captions": m.captions},
            "like_count": p.like_count,
            "comment_count": p.comment_count,
            "liked": p.id in liked,
            "mine": viewer is not None and viewer.id == p.user_id,
        }
        for p, m in rows
    ]


def hot_score(post: Post, now: datetime) -> float:
    """Kiểu Hacker News: tương tác chia cho tuổi bài, bình luận nặng hơn tim."""
    hours = (now - _aware(post.created_at)).total_seconds() / 3600
    return (post.like_count + 2 * post.comment_count + 1) / math.pow(hours + 2, 1.5)


def _get_post(session: Session, post_id: str) -> tuple[Post, Meme]:
    row = session.execute(_visible(select(Post, Meme)).where(Post.id == post_id)).first()
    if not row:
        raise ApiError(404, "not_found", "Bài viết không tồn tại hoặc đã bị gỡ")
    return row[0], row[1]


# ---------- bài viết ----------


class CreatePost(BaseModel):
    meme_id: str
    caption: str = Field(default="", max_length=MAX_CAPTION)


@router.post("/posts")
@limiter.limit(lambda: get_settings().rate_limit_posts)
def create_post(
    request: Request, body: CreatePost, user: User = Depends(require_user), session: Session = Depends(get_session)
):
    meme = session.get(Meme, body.meme_id)
    if not meme or meme.deleted:
        raise ApiError(404, "not_found", "Không tìm thấy meme")
    if meme.user_id != user.id:
        raise ApiError(403, "forbidden", "Chỉ chia sẻ được meme do bạn tạo")
    if meme.hidden:
        raise ApiError(403, "hidden", "Meme đang bị báo cáo nên chưa chia sẻ được")
    if meme.rank is None and meme.parent_id is None:
        raise ApiError(400, "invalid_input", "Chỉ chia sẻ được meme kết quả")
    if existing := session.scalar(select(Post).where(Post.meme_id == meme.id)):
        if existing.hidden:
            raise ApiError(403, "hidden", "Bài viết của meme này đã bị gỡ do báo cáo")
        return posts_out(session, [(existing, meme)], user)[0]
    post = Post(user_id=user.id, meme_id=meme.id, caption=body.caption.strip())
    session.add(post)
    try:
        session.commit()
    except IntegrityError:  # bấm đăng hai lần cùng lúc
        session.rollback()
        post = session.scalar(select(Post).where(Post.meme_id == meme.id))
    return posts_out(session, [(post, meme)], user)[0]


@router.get("/feed")
def feed(
    sort: str = "new",
    before: str | None = None,
    user: User | None = Depends(optional_user),
    session: Session = Depends(get_session),
):
    if sort == "hot":
        since = datetime.now(UTC) - timedelta(days=HOT_WINDOW_DAYS)
        rows = session.execute(_visible(select(Post, Meme)).where(Post.created_at >= since)).all()
        now = datetime.now(UTC)
        rows = sorted(rows, key=lambda r: -hot_score(r[0], now))[:50]
        return {"items": posts_out(session, [tuple(r) for r in rows], user), "next_before": None}
    query = _visible(select(Post, Meme))
    if before:
        try:
            query = query.where(Post.created_at < datetime.fromisoformat(before))
        except ValueError as e:
            raise ApiError(400, "invalid_input", "Tham số before không hợp lệ") from e
    rows = session.execute(query.order_by(Post.created_at.desc()).limit(PAGE_SIZE + 1)).all()
    items = posts_out(session, [tuple(r) for r in rows[:PAGE_SIZE]], user)
    return {"items": items, "next_before": items[-1]["created_at"] if len(rows) > PAGE_SIZE else None}


@router.get("/users/{username}/posts")
def user_posts(username: str, user: User | None = Depends(optional_user), session: Session = Depends(get_session)):
    author = session.scalar(select(User).where(User.username == username.lower()))
    if not author or author.is_banned:
        raise ApiError(404, "not_found", "Không tìm thấy người dùng")
    rows = session.execute(
        _visible(select(Post, Meme)).where(Post.user_id == author.id).order_by(Post.created_at.desc()).limit(50)
    ).all()
    return {"items": posts_out(session, [tuple(r) for r in rows], user)}


@router.get("/posts/{post_id}")
def get_post(post_id: str, user: User | None = Depends(optional_user), session: Session = Depends(get_session)):
    post, meme = _get_post(session, post_id)
    comments = session.scalars(
        select(Comment).where(Comment.post_id == post.id).order_by(Comment.created_at).limit(200)
    ).all()
    users = {u.id: u for u in session.scalars(select(User).where(User.id.in_({c.user_id for c in comments})))}
    return posts_out(session, [(post, meme)], user)[0] | {
        "comments": [
            {
                "id": c.id,
                "created_at": _aware(c.created_at).isoformat(),
                "body": c.body,
                "author": author_out(users.get(c.user_id)),
                # chủ bình luận và chủ bài đều xoá được
                "can_delete": user is not None and user.id in (c.user_id, post.user_id),
            }
            for c in comments
        ]
    }


class EditPost(BaseModel):
    caption: str = Field(max_length=MAX_CAPTION)


@router.patch("/posts/{post_id}")
def edit_post(
    post_id: str, body: EditPost, user: User = Depends(require_user), session: Session = Depends(get_session)
):
    post, meme = _get_post(session, post_id)
    if post.user_id != user.id:
        raise ApiError(403, "forbidden", "Chỉ người đăng mới sửa được")
    post.caption = body.caption.strip()
    post.edited_at = datetime.now(UTC)
    session.commit()
    return posts_out(session, [(post, meme)], user)[0]


@router.delete("/posts/{post_id}", status_code=204)
def delete_post(post_id: str, user: User = Depends(require_user), session: Session = Depends(get_session)):
    post = session.get(Post, post_id)
    if not post:
        raise ApiError(404, "not_found", "Bài viết không tồn tại")
    if post.user_id != user.id:
        raise ApiError(403, "forbidden", "Chỉ người đăng mới xoá được")
    remove_posts(session, [post.id])
    session.commit()
    return Response(status_code=204)


def remove_posts(session: Session, ids: list[str]) -> None:
    if not ids:
        return
    session.execute(delete(PostLike).where(PostLike.post_id.in_(ids)))
    session.execute(delete(Comment).where(Comment.post_id.in_(ids)))
    session.execute(delete(Post).where(Post.id.in_(ids)))


class ReportIn(BaseModel):
    reason: str = Field(default="", max_length=300)


@router.post("/posts/{post_id}/report", status_code=204)
def report_post(post_id: str, body: ReportIn, session: Session = Depends(get_session)):
    post = session.get(Post, post_id)
    if not post:
        raise ApiError(404, "not_found", "Bài viết không tồn tại")
    post.reported += 1
    if post.reported >= get_settings().report_hide_threshold:
        post.hidden = True
    session.commit()
    return Response(status_code=204)


# ---------- tim ----------


def _like_response(session: Session, post: Post, liked: bool) -> dict:
    session.refresh(post)
    return {"liked": liked, "like_count": post.like_count}


@router.post("/posts/{post_id}/like")
def like(post_id: str, user: User = Depends(require_user), session: Session = Depends(get_session)):
    post, _ = _get_post(session, post_id)
    if not session.get(PostLike, (post.id, user.id)):
        session.add(PostLike(post_id=post.id, user_id=user.id))
        try:
            session.flush()
            session.execute(update(Post).where(Post.id == post.id).values(like_count=Post.like_count + 1))
            session.commit()
        except IntegrityError:  # hai lần bấm cùng lúc
            session.rollback()
    return _like_response(session, post, True)


@router.delete("/posts/{post_id}/like")
def unlike(post_id: str, user: User = Depends(require_user), session: Session = Depends(get_session)):
    post, _ = _get_post(session, post_id)
    deleted = session.execute(delete(PostLike).where(PostLike.post_id == post.id, PostLike.user_id == user.id))
    if deleted.rowcount:
        session.execute(update(Post).where(Post.id == post.id).values(like_count=Post.like_count - 1))
    session.commit()
    return _like_response(session, post, False)


# ---------- bình luận ----------


class CreateComment(BaseModel):
    body: str = Field(min_length=1, max_length=MAX_COMMENT)


@router.post("/posts/{post_id}/comments")
@limiter.limit(lambda: get_settings().rate_limit_comments)
def create_comment(
    request: Request,
    post_id: str,
    body: CreateComment,
    user: User = Depends(require_user),
    session: Session = Depends(get_session),
):
    post, _ = _get_post(session, post_id)
    text = " ".join(body.body.split())
    if not text:
        raise ApiError(400, "invalid_input", "Bình luận không được để trống")
    comment = Comment(post_id=post.id, user_id=user.id, body=text)
    session.add(comment)
    session.execute(update(Post).where(Post.id == post.id).values(comment_count=Post.comment_count + 1))
    session.commit()
    return {
        "id": comment.id,
        "created_at": _aware(comment.created_at).isoformat(),
        "body": comment.body,
        "author": author_out(user),
        "can_delete": True,
    }


@router.delete("/comments/{comment_id}", status_code=204)
def delete_comment(comment_id: str, user: User = Depends(require_user), session: Session = Depends(get_session)):
    comment = session.get(Comment, comment_id)
    if not comment:
        raise ApiError(404, "not_found", "Bình luận không tồn tại")
    post = session.get(Post, comment.post_id)
    if user.id not in (comment.user_id, post.user_id if post else None):
        raise ApiError(403, "forbidden", "Bạn không xoá được bình luận này")
    session.delete(comment)
    if post:
        session.execute(update(Post).where(Post.id == post.id).values(comment_count=Post.comment_count - 1))
    session.commit()
    return Response(status_code=204)
