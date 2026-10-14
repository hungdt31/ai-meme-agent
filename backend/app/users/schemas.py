from pydantic import BaseModel, Field

from app.memes.schemas import MemeWithTopic


class GoogleLogin(BaseModel):
    credential: str = Field(min_length=20, max_length=4096)


class UpdateMe(BaseModel):
    display_name: str | None = Field(default=None, min_length=1, max_length=60)
    username: str | None = None
    profile_public: bool | None = None


# ---------- response ----------


class QuotaOut(BaseModel):
    limit: int
    used: int
    left: int


class GuestQuotaOut(QuotaOut):
    signed_in: bool


class StatsOut(BaseModel):
    memes: int
    posts: int
    likes: int


class MeOut(BaseModel):
    id: str
    username: str
    display_name: str
    avatar_url: str | None
    email: str  # chỉ trả cho chính chủ
    profile_public: bool
    created_at: str
    stats: StatsOut
    quota: QuotaOut


class LoginOut(BaseModel):
    token: str
    expires_at: str
    user: MeOut


class MemePage(BaseModel):
    """Phân trang theo số trang (trang Meme của tôi)."""

    items: list[MemeWithTopic]
    page: int
    pages: int
    total: int
    page_size: int


class MemeCursorPage(BaseModel):
    items: list[MemeWithTopic]
    next_before: str | None


class PublicProfileOut(BaseModel):
    username: str
    display_name: str
    avatar_url: str | None
    joined_at: str
    meme_count: int
    memes: MemeCursorPage
