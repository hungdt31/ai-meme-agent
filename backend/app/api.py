import io
import json
from typing import Literal

from fastapi import APIRouter, Depends, File, Request, UploadFile
from fastapi.responses import Response, StreamingResponse
from PIL import Image, UnidentifiedImageError
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from agent.prompts import STYLES
from app.auth.deps import optional_user, require_user
from app.core.config import get_settings
from app.core.db import get_session, new_id
from app.core.errors import ApiError
from app.core.limits import limiter
from app.core.security import client_hash
from app.core.storage import get_storage
from app.memes.quota import get_quota
from app.models import Job, Meme, User
from app.service import delete_meme_files, meme_out, save_meme_image, stream_job
from app.social import post_ids
from render.renderer import prepare_upload, render_meme
from render.templates import IMAGE_DIR, Box, get_template, load_templates

router = APIRouter(prefix="/api")
ALLOWED_TYPES = {"image/jpeg", "image/png", "image/webp"}


# ---------- uploads ----------


@router.post("/uploads")
@limiter.limit(lambda: get_settings().rate_limit_uploads)
async def upload(request: Request, file: UploadFile = File(...)):
    s = get_settings()
    if file.content_type not in ALLOWED_TYPES:
        raise ApiError(415, "unsupported_type", "Chỉ nhận ảnh JPG, PNG hoặc WebP")
    data = await file.read(s.max_upload_mb * 1024 * 1024 + 1)
    if len(data) > s.max_upload_mb * 1024 * 1024:
        raise ApiError(413, "file_too_large", f"Ảnh tối đa {s.max_upload_mb} MB")
    try:
        clean = prepare_upload(data, s.max_upload_px)
    except (UnidentifiedImageError, OSError) as e:
        raise ApiError(400, "invalid_input", "Không đọc được ảnh") from e
    upload_id = new_id(16)
    get_storage().put(f"uploads/{upload_id}.webp", clean)
    return {"upload_id": upload_id}


# ---------- jobs ----------


class CreateJob(BaseModel):
    topic: str | None = Field(default=None, max_length=300)
    upload_id: str | None = Field(default=None, pattern=r"^[\w-]{6,32}$")
    template_id: str | None = None
    style: Literal["gen_z", "van_phong", "mua_thi", "choi_chu"] | None = None
    consent: bool = False  # người dùng xác nhận có quyền dùng ảnh tải lên


@router.post("/jobs")
def create_job(
    request: Request,
    body: CreateJob,
    user: User | None = Depends(optional_user),
    session: Session = Depends(get_session),
):
    topic = (body.topic or "").strip() or None
    if not topic and not body.upload_id:
        raise ApiError(400, "invalid_input", "Cần nhập tình huống hoặc tải ảnh lên")
    if body.upload_id and not body.consent:
        raise ApiError(400, "invalid_input", "Cần xác nhận bạn có quyền dùng ảnh này")
    if body.template_id and not get_template(body.template_id):
        raise ApiError(400, "invalid_input", "Template không tồn tại")
    if body.upload_id and body.template_id:
        raise ApiError(400, "invalid_input", "Chọn ảnh tải lên hoặc template, không chọn cả hai")
    chash = client_hash(request)
    quota = get_quota(session, user, chash)
    if quota.left <= 0:
        message = (
            f"Bạn đã dùng hết {quota.limit} lượt trong 24 giờ, quay lại sau nhé"
            if user
            else f"Khách được {quota.limit} lượt mỗi ngày. Đăng nhập Google để có thêm lượt"
        )
        raise ApiError(429, "quota_exceeded", message)
    job = Job(
        input_type="upload" if body.upload_id else ("template" if body.template_id else "topic"),
        topic=topic,
        upload_key=f"uploads/{body.upload_id}.webp" if body.upload_id else None,
        template_id=body.template_id,
        style=body.style,
        client_hash=chash,
        user_id=user.id if user else None,
    )
    session.add(job)
    session.commit()
    return {"job_id": job.id}


@router.post("/jobs/{job_id}/run")
def run_job(job_id: str, session: Session = Depends(get_session)):
    job = session.get(Job, job_id)
    if not job:
        raise ApiError(404, "not_found", "Không tìm thấy job")
    if job.status != "created":
        raise ApiError(409, "already_running", "Job này đã chạy rồi")
    job.status = "running"
    session.commit()

    async def events():
        async for event in stream_job(job_id):
            yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        events(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
    )


@router.get("/jobs/{job_id}")
def get_job(job_id: str, session: Session = Depends(get_session)):
    job = session.get(Job, job_id)
    if not job:
        raise ApiError(404, "not_found", "Không tìm thấy job")
    memes = session.scalars(
        select(Meme)
        .where(Meme.job_id == job_id, Meme.rank.is_not(None), Meme.hidden.is_(False), Meme.deleted.is_(False))
        .order_by(Meme.rank)
    ).all()
    owner = session.get(User, job.user_id) if job.user_id else None
    return {
        "id": job.id,
        "status": job.status,
        "topic": job.topic,
        "style": job.style,
        "error": job.error,
        "memes": [meme_out(m, owner) for m in memes],
    }


# ---------- memes ----------


def _get_meme(session: Session, meme_id: str) -> Meme:
    m = session.get(Meme, meme_id)
    if not m:
        raise ApiError(404, "not_found", "Không tìm thấy meme")
    if m.deleted:
        raise ApiError(410, "deleted", "Meme đã bị chủ xoá")
    if m.hidden:
        raise ApiError(410, "hidden", "Meme đang được xem xét")
    return m


def _require_owner(m: Meme, user: User | None) -> None:
    """Meme có chủ thì chỉ chủ được sửa hoặc xoá. Meme của khách thì ai có link job cũng sửa được."""
    if m.user_id and (user is None or user.id != m.user_id):
        raise ApiError(403, "forbidden", "Chỉ người tạo meme này mới sửa hoặc xoá được")


@router.get("/memes/{meme_id}")
def get_meme(meme_id: str, session: Session = Depends(get_session)):
    m = _get_meme(session, meme_id)
    job = session.get(Job, m.job_id)
    owner = session.get(User, m.user_id) if m.user_id else None
    return meme_out(m, owner, post_id=post_ids(session, [m.id]).get(m.id)) | {"topic": job.topic if job else None}


class Rerender(BaseModel):
    captions: dict[str, str]


@router.post("/memes/{meme_id}/rerender")
@limiter.limit(lambda: get_settings().rate_limit_rerender)
def rerender(
    request: Request,
    meme_id: str,
    body: Rerender,
    user: User | None = Depends(optional_user),
    session: Session = Depends(get_session),
):
    s = get_settings()
    m = _get_meme(session, meme_id)
    _require_owner(m, user)
    boxes = [Box.model_validate(b) for b in m.boxes]
    storage = get_storage()
    if m.template_id:
        template = get_template(m.template_id)
        if not template:
            raise ApiError(410, "base_expired", "Template không còn")
        base = template.load_image()
    else:
        try:
            base = Image.open(io.BytesIO(storage.get(m.base_key)))
        except Exception as e:  # noqa: BLE001 - ảnh tải lên bị xoá sau 24 giờ
            raise ApiError(410, "base_expired", "Ảnh gốc đã hết hạn lưu, hãy tải lại") from e
    captions = {b.id: body.captions.get(b.id, m.captions.get(b.id, ""))[: s.max_caption_chars] for b in boxes}
    result = render_meme(base, boxes, captions)
    new = Meme(
        id=new_id(),
        job_id=m.job_id,
        template_id=m.template_id,
        base_key=m.base_key,
        boxes=m.boxes,
        captions=captions,
        image_key="",
        variant=m.variant,
        parent_id=m.id,
        user_id=m.user_id,
    )
    new.image_key = f"memes/{new.id}.webp"
    save_meme_image(new.image_key, result.data)
    session.add(new)
    session.commit()
    owner = session.get(User, new.user_id) if new.user_id else None
    return meme_out(new, owner) | {"overflow": result.overflow, "overflow_boxes": result.overflow_boxes}


@router.delete("/memes/{meme_id}", status_code=204)
def delete_meme(meme_id: str, user: User = Depends(require_user), session: Session = Depends(get_session)):
    m = session.get(Meme, meme_id)
    if not m or m.deleted:
        raise ApiError(404, "not_found", "Không tìm thấy meme")
    _require_owner(m, user)
    m.deleted = True
    delete_meme_files(m)
    session.commit()
    return Response(status_code=204)


class Report(BaseModel):
    reason: str = Field(default="", max_length=300)


@router.post("/memes/{meme_id}/report", status_code=204)
def report(meme_id: str, body: Report, session: Session = Depends(get_session)):
    m = session.get(Meme, meme_id)
    if not m:
        raise ApiError(404, "not_found", "Không tìm thấy meme")
    m.reported += 1
    if m.reported >= get_settings().report_hide_threshold and not m.hidden:
        m.hidden = True
        delete_meme_files(m)  # gỡ khỏi đường dẫn public
    session.commit()
    return Response(status_code=204)


# ---------- khác ----------


@router.get("/templates")
def templates():
    base = get_settings().public_base_url.rstrip("/")
    return [
        {"id": t.id, "name": t.name, "when_to_use": t.when_to_use, "thumb_url": f"{base}/static/templates/{t.image}"}
        for t in load_templates().values()
        if (IMAGE_DIR / t.image).exists()
    ]


@router.get("/styles")
def styles():
    return [{"id": k, "label": v.split(":")[0]} for k, v in STYLES.items()]


@router.get("/health")
def health():
    from agent.llm import get_llm

    llm = get_llm()
    models = llm.status() if hasattr(llm, "status") else []
    return {"status": "ok", "fake_llm": get_settings().use_fake_llm, "models": models}
