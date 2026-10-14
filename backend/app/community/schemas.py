from pydantic import BaseModel, Field

from app.auth.models import User
from app.community.models import Comment, Post
from app.core.storage import get_storage
from app.core.time import aware
from app.memes.models import Meme

MAX_CAPTION = 500
MAX_COMMENT = 500


class CreatePost(BaseModel):
    meme_id: str
    caption: str = Field(default="", max_length=MAX_CAPTION)


class EditPost(BaseModel):
    caption: str = Field(max_length=MAX_CAPTION)


class ReportIn(BaseModel):
    reason: str = Field(default="", max_length=300)


class CreateComment(BaseModel):
    body: str = Field(min_length=1, max_length=MAX_COMMENT)


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


def post_out(p: Post, m: Meme, author: User | None, *, liked: bool, mine: bool) -> dict:
    return {
        "id": p.id,
        "created_at": aware(p.created_at).isoformat(),
        "edited": p.edited_at is not None,
        "caption": p.caption,
        "author": author_out(author),
        "meme": {"id": m.id, "image_url": get_storage().url(m.image_key), "captions": m.captions},
        "like_count": p.like_count,
        "comment_count": p.comment_count,
        "liked": liked,
        "mine": mine,
    }


def comment_out(c: Comment, author: User | None, *, can_delete: bool) -> dict:
    return {
        "id": c.id,
        "created_at": aware(c.created_at).isoformat(),
        "body": c.body,
        "author": author_out(author),
        "can_delete": can_delete,
    }
