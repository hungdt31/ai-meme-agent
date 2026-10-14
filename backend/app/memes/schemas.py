from typing import Literal

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


def owner_out(user: User | None) -> dict | None:
    """Thông tin công khai của chủ meme. Hồ sơ riêng tư thì không lộ ai là người tạo."""
    if user is None or not user.profile_public:
        return None
    return {"username": user.username, "display_name": user.display_name, "avatar_url": user.avatar_url}


def meme_out(m: Meme, owner: User | None = None, post_id: str | None = None) -> dict:
    return {
        "id": m.id,
        "job_id": m.job_id,
        "image_url": get_storage().url(m.image_key),
        "og_image_url": get_storage().url(og_key(m.image_key)),
        "template_id": m.template_id,
        "captions": m.captions,
        "boxes": [
            {"id": b["id"], "style": b["style"], "max_chars": b["max_chars"], "hint": b.get("hint", "")}
            for b in m.boxes
        ],
        "scores": m.scores,
        "rank": m.rank,
        "parent_id": m.parent_id,
        "hidden": m.hidden,
        "owner": owner_out(owner),
        "owner_id": m.user_id,  # id ngẫu nhiên, để frontend biết meme có phải của mình (kể cả hồ sơ riêng tư)
        "post_id": post_id,  # đã chia sẻ lên cộng đồng thì là id bài viết
        "created_at": m.created_at.isoformat(),
    }
