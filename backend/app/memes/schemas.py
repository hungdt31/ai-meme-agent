from typing import Any, Literal, Self

from pydantic import BaseModel, Field

from app.auth.models import User
from app.core.storage import get_storage
from app.memes.models import Meme


class CreateJob(BaseModel):
    topic: str | None = Field(default=None, max_length=300)
    upload_id: str | None = Field(default=None, pattern=r"^[\w-]{6,32}$")
    template_id: str | None = None
    style: Literal["gen_z", "van_phong", "mua_thi", "choi_chu"] | None = None
    consent: bool = False  # người dùng xác nhận có quyền dùng ảnh tải lên


class Rerender(BaseModel):
    captions: dict[str, str]


class Report(BaseModel):
    reason: str = Field(default="", max_length=300)


def og_key(image_key: str) -> str:
    return image_key.rsplit(".", 1)[0] + ".jpg"


# ---------- response ----------


class BoxOut(BaseModel):
    id: str
    style: str
    max_chars: int
    hint: str = ""


class OwnerOut(BaseModel):
    """Thông tin công khai của chủ meme."""

    username: str
    display_name: str
    avatar_url: str | None


class MemeOut(BaseModel):
    id: str
    job_id: str
    image_url: str
    og_image_url: str
    template_id: str | None
    captions: dict[str, str]
    boxes: list[BoxOut]
    scores: dict[str, Any] | None
    rank: int | None
    parent_id: str | None
    hidden: bool
    owner: OwnerOut | None
    owner_id: str | None  # id ngẫu nhiên, để frontend biết meme có phải của mình (kể cả hồ sơ riêng tư)
    post_id: str | None  # đã chia sẻ lên cộng đồng thì là id bài viết
    created_at: str

    @classmethod
    def of(cls, m: Meme, owner: User | None = None, post_id: str | None = None, **extra: Any) -> Self:
        storage = get_storage()
        return cls(
            id=m.id,
            job_id=m.job_id,
            image_url=storage.url(m.image_key),
            og_image_url=storage.url(og_key(m.image_key)),
            template_id=m.template_id,
            captions=m.captions,
            boxes=[BoxOut.model_validate(b) for b in m.boxes],  # bỏ toạ độ, chỉ giữ thông tin cho ô sửa chữ
            scores=m.scores,
            rank=m.rank,
            parent_id=m.parent_id,
            hidden=m.hidden,
            # Hồ sơ riêng tư thì không lộ ai là người tạo
            owner=OwnerOut.model_validate(owner, from_attributes=True) if owner and owner.profile_public else None,
            owner_id=m.user_id,
            post_id=post_id,
            created_at=m.created_at.isoformat(),
            **extra,
        )


class MemeWithTopic(MemeOut):
    topic: str | None


class RerenderOut(MemeOut):
    overflow: bool
    overflow_boxes: list[str]


class UploadOut(BaseModel):
    upload_id: str


class JobCreated(BaseModel):
    job_id: str


class JobOut(BaseModel):
    id: str
    status: str  # created | running | done | refused | failed
    topic: str | None
    style: str | None
    error: str | None
    memes: list[MemeOut]


class TemplateOut(BaseModel):
    id: str
    name: str
    when_to_use: str
    thumb_url: str


class StyleOut(BaseModel):
    id: str
    label: str
