"""Cộng đồng kiểu Threads: đăng meme của mình kèm caption, bảng tin, thả tim, bình luận."""

from fastapi import APIRouter, Depends, Request
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.auth.deps import optional_user, require_user
from app.auth.models import User
from app.community import service
from app.community.schemas import CreateComment, CreatePost, EditPost, ReportIn, comment_out
from app.core.config import get_settings
from app.core.db import get_session
from app.core.limits import limiter
from app.core.time import parse_before

router = APIRouter(prefix="/api")


# ---------- bảng tin ----------


@router.get("/feed")
def feed(
    sort: str = "new",
    before: str | None = None,
    user: User | None = Depends(optional_user),
    session: Session = Depends(get_session),
):
    if sort == "hot":
        return {"items": service.posts_view(session, service.feed_hot(session), user), "next_before": None}
    rows, more = service.feed_new(session, parse_before(before))
    items = service.posts_view(session, rows, user)
    return {"items": items, "next_before": items[-1]["created_at"] if more else None}


@router.get("/users/{username}/posts")
def user_posts(username: str, user: User | None = Depends(optional_user), session: Session = Depends(get_session)):
    return {"items": service.posts_view(session, service.posts_by(session, username), user)}


# ---------- bài viết ----------


@router.post("/posts")
@limiter.limit(lambda: get_settings().rate_limit_posts)
def create_post(
    request: Request, body: CreatePost, user: User = Depends(require_user), session: Session = Depends(get_session)
):
    row = service.create_post(session, user, body.meme_id, body.caption)
    return service.posts_view(session, [row], user)[0]


@router.get("/posts/{post_id}")
def get_post(post_id: str, user: User | None = Depends(optional_user), session: Session = Depends(get_session)):
    post, meme = service.get_post(session, post_id)
    return service.posts_view(session, [(post, meme)], user)[0] | {
        "comments": service.comments_view(session, post, user)
    }


@router.patch("/posts/{post_id}")
def edit_post(
    post_id: str, body: EditPost, user: User = Depends(require_user), session: Session = Depends(get_session)
):
    row = service.edit_post(session, user, post_id, body.caption)
    return service.posts_view(session, [row], user)[0]


@router.delete("/posts/{post_id}", status_code=204)
def delete_post(post_id: str, user: User = Depends(require_user), session: Session = Depends(get_session)):
    service.delete_post(session, user, post_id)
    return Response(status_code=204)


@router.post("/posts/{post_id}/report", status_code=204)
def report_post(post_id: str, body: ReportIn, session: Session = Depends(get_session)):
    service.report_post(session, post_id)
    return Response(status_code=204)


# ---------- tim ----------


@router.post("/posts/{post_id}/like")
def like(post_id: str, user: User = Depends(require_user), session: Session = Depends(get_session)):
    return {"liked": True, "like_count": service.set_like(session, user, post_id, True)}


@router.delete("/posts/{post_id}/like")
def unlike(post_id: str, user: User = Depends(require_user), session: Session = Depends(get_session)):
    return {"liked": False, "like_count": service.set_like(session, user, post_id, False)}


# ---------- bình luận ----------


@router.post("/posts/{post_id}/comments")
@limiter.limit(lambda: get_settings().rate_limit_comments)
def create_comment(
    request: Request,
    post_id: str,
    body: CreateComment,
    user: User = Depends(require_user),
    session: Session = Depends(get_session),
):
    comment = service.add_comment(session, user, post_id, body.body)
    return comment_out(comment, user, can_delete=True)


@router.delete("/comments/{comment_id}", status_code=204)
def delete_comment(comment_id: str, user: User = Depends(require_user), session: Session = Depends(get_session)):
    service.delete_comment(session, user, comment_id)
    return Response(status_code=204)
