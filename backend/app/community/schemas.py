from typing import Self

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


# ---------- response ----------


class AuthorOut(BaseModel):
    """Đăng bài là hành động công khai nên luôn hiện tên; chỉ có link hồ sơ khi hồ sơ để công khai."""

    username: str | None
    display_name: str
    avatar_url: str | None
    profile_public: bool

    @classmethod
    def of(cls, user: User | None) -> Self:
        if user is None:
            return cls(username=None, display_name="Tài khoản đã xoá", avatar_url=None, profile_public=False)
        return cls.model_validate(user, from_attributes=True)


class PostMemeOut(BaseModel):
    id: str
    image_url: str
    captions: dict[str, str]


class PostOut(BaseModel):
    id: str
    created_at: str
    edited: bool
    caption: str
    author: AuthorOut
    meme: PostMemeOut
    like_count: int
    comment_count: int
    liked: bool  # người xem đã thả tim
    mine: bool  # người xem là người đăng

    @classmethod
    def of(cls, p: Post, m: Meme, author: User | None, *, liked: bool, mine: bool) -> Self:
        return cls(
            id=p.id,
            created_at=aware(p.created_at).isoformat(),
            edited=p.edited_at is not None,
            caption=p.caption,
            author=AuthorOut.of(author),
            meme=PostMemeOut(id=m.id, image_url=get_storage().url(m.image_key), captions=m.captions),
            like_count=p.like_count,
            comment_count=p.comment_count,
            liked=liked,
            mine=mine,
        )


class CommentOut(BaseModel):
    id: str
    created_at: str
    body: str
    author: AuthorOut
    can_delete: bool  # chủ bình luận và chủ bài đều xoá được

    @classmethod
    def of(cls, c: Comment, author: User | None, *, can_delete: bool) -> Self:
        return cls(
            id=c.id,
            created_at=aware(c.created_at).isoformat(),
            body=c.body,
            author=AuthorOut.of(author),
            can_delete=can_delete,
        )


class PostDetail(PostOut):
    comments: list[CommentOut]


class FeedPage(BaseModel):
    items: list[PostOut]
    next_before: str | None


class PostList(BaseModel):
    items: list[PostOut]


class LikeOut(BaseModel):
    liked: bool
    like_count: int
