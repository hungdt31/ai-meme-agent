"""Nghiệp vụ meme: tạo job, sửa chữ, xoá, báo cáo, lưu ảnh và danh sách meme của một người."""

import io
from datetime import datetime

from PIL import Image, UnidentifiedImageError
from sqlalchemy import func, or_, select, update
from sqlalchemy.orm import Session

from agent.state import Candidate
from app.auth.models import User
from app.core.config import get_settings
from app.core.db import new_id
from app.core.errors import ApiError
from app.core.storage import get_storage
from app.memes.models import Job, Meme
from app.memes.quota import get_quota
from app.memes.schemas import CreateJob, og_key
from render.renderer import RenderResult, prepare_upload, render_meme, to_jpeg
from render.templates import UPLOAD_LAYOUTS, Box, get_template

ALLOWED_TYPES = {"image/jpeg", "image/png", "image/webp"}


# ---------- ảnh ----------


def save_meme_image(key: str, webp: bytes) -> None:
    storage = get_storage()
    storage.put(key, webp)
    storage.put(og_key(key), to_jpeg(webp), content_type="image/jpeg")


def delete_meme_files(m: Meme) -> None:
    storage = get_storage()
    storage.delete(m.image_key)
    storage.delete(og_key(m.image_key))


def save_upload(data: bytes, content_type: str | None) -> str:
    """Kiểm tra, bỏ EXIF và lưu ảnh tải lên. Trả về upload_id."""
    s = get_settings()
    if content_type not in ALLOWED_TYPES:
        raise ApiError(415, "unsupported_type", "Chỉ nhận ảnh JPG, PNG hoặc WebP")
    if len(data) > s.max_upload_mb * 1024 * 1024:
        raise ApiError(413, "file_too_large", f"Ảnh tối đa {s.max_upload_mb} MB")
    try:
        clean = prepare_upload(data, s.max_upload_px)
    except (UnidentifiedImageError, OSError) as e:
        raise ApiError(400, "invalid_input", "Không đọc được ảnh") from e
    upload_id = new_id(16)
    get_storage().put(f"uploads/{upload_id}.webp", clean)
    return upload_id


# ---------- job ----------


def create_job(session: Session, body: CreateJob, user: User | None, client_hash: str) -> Job:
    topic = (body.topic or "").strip() or None
    if not topic and not body.upload_id:
        raise ApiError(400, "invalid_input", "Cần nhập tình huống hoặc tải ảnh lên")
    if body.upload_id and not body.consent:
        raise ApiError(400, "invalid_input", "Cần xác nhận bạn có quyền dùng ảnh này")
    if body.template_id and not get_template(body.template_id):
        raise ApiError(400, "invalid_input", "Template không tồn tại")
    if body.upload_id and body.template_id:
        raise ApiError(400, "invalid_input", "Chọn ảnh tải lên hoặc template, không chọn cả hai")
    quota = get_quota(session, user, client_hash)
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
        client_hash=client_hash,
        user_id=user.id if user else None,
    )
    session.add(job)
    session.commit()
    return job


def get_job(session: Session, job_id: str) -> Job:
    job = session.get(Job, job_id)
    if not job:
        raise ApiError(404, "not_found", "Không tìm thấy job")
    return job


def start_job(session: Session, job_id: str) -> Job:
    job = get_job(session, job_id)
    if job.status != "created":
        raise ApiError(409, "already_running", "Job này đã chạy rồi")
    job.status = "running"
    session.commit()
    return job


def job_results(session: Session, job_id: str) -> list[Meme]:
    return list(
        session.scalars(
            select(Meme)
            .where(Meme.job_id == job_id, Meme.rank.is_not(None), Meme.hidden.is_(False), Meme.deleted.is_(False))
            .order_by(Meme.rank)
        )
    )


def persist_winners(
    session: Session, job: Job, winners: list[Candidate], text_layout: str = "top_bottom"
) -> list[Meme]:
    storage = get_storage()
    memes = []
    for rank, c in enumerate(winners, start=1):
        meme_id = new_id()
        key = f"memes/{meme_id}.webp"
        save_meme_image(key, storage.get(c.image_key))
        template = get_template(c.template_id) if c.template_id else None
        boxes = template.boxes if template else UPLOAD_LAYOUTS[text_layout]
        m = Meme(
            id=meme_id,
            job_id=job.id,
            template_id=c.template_id,
            base_key=None if template else job.upload_key,
            boxes=[b.model_dump() for b in boxes],
            captions=c.captions,
            image_key=key,
            scores=c.scores,
            variant=job.variant,
            rank=rank,
            user_id=job.user_id,
        )
        session.add(m)
        memes.append(m)
    return memes


# ---------- meme ----------


def get_visible_meme(session: Session, meme_id: str) -> Meme:
    m = session.get(Meme, meme_id)
    if not m:
        raise ApiError(404, "not_found", "Không tìm thấy meme")
    if m.deleted:
        raise ApiError(410, "deleted", "Meme đã bị chủ xoá")
    if m.hidden:
        raise ApiError(410, "hidden", "Meme đang được xem xét")
    return m


def require_owner(m: Meme, user: User | None) -> None:
    """Meme có chủ thì chỉ chủ được sửa hoặc xoá. Meme của khách thì ai có link job cũng sửa được."""
    if m.user_id and (user is None or user.id != m.user_id):
        raise ApiError(403, "forbidden", "Chỉ người tạo meme này mới sửa hoặc xoá được")


def rerender(session: Session, m: Meme, new_captions: dict[str, str]) -> tuple[Meme, RenderResult]:
    """Vẽ lại meme với chữ mới thành một meme con (giữ bản gốc)."""
    boxes = [Box.model_validate(b) for b in m.boxes]
    if m.template_id:
        template = get_template(m.template_id)
        if not template:
            raise ApiError(410, "base_expired", "Template không còn")
        base = template.load_image()
    else:
        try:
            base = Image.open(io.BytesIO(get_storage().get(m.base_key)))
        except Exception as e:  # noqa: BLE001 - ảnh tải lên bị xoá sau 24 giờ
            raise ApiError(410, "base_expired", "Ảnh gốc đã hết hạn lưu, hãy tải lại") from e
    limit = get_settings().max_caption_chars
    captions = {b.id: new_captions.get(b.id, m.captions.get(b.id, ""))[:limit] for b in boxes}
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
    return new, result


def delete_meme(session: Session, meme_id: str, user: User) -> None:
    m = session.get(Meme, meme_id)
    if not m or m.deleted:
        raise ApiError(404, "not_found", "Không tìm thấy meme")
    require_owner(m, user)
    m.deleted = True
    delete_meme_files(m)
    session.commit()


def report_meme(session: Session, meme_id: str) -> None:
    m = session.get(Meme, meme_id)
    if not m:
        raise ApiError(404, "not_found", "Không tìm thấy meme")
    m.reported += 1
    if m.reported >= get_settings().report_hide_threshold and not m.hidden:
        m.hidden = True
        delete_meme_files(m)  # gỡ khỏi đường dẫn public
    session.commit()


# ---------- meme của một người ----------


def _owned_final(user_id: str) -> tuple:
    """Meme kết quả (top 3 của job hoặc bản đã sửa) còn hiển thị của một người."""
    return (
        Meme.user_id == user_id,
        Meme.hidden.is_(False),
        Meme.deleted.is_(False),
        or_(Meme.rank.is_not(None), Meme.parent_id.is_not(None)),
    )


def count_owned(session: Session, user_id: str) -> int:
    return session.scalar(select(func.count()).select_from(Meme).where(*_owned_final(user_id))) or 0


def list_owned(
    session: Session, user_id: str, *, limit: int, offset: int = 0, before: datetime | None = None
) -> list[tuple[Meme, str | None]]:
    """(meme, topic của job) mới nhất trước."""
    query = select(Meme, Job.topic).join(Job, Job.id == Meme.job_id).where(*_owned_final(user_id))
    if before:
        query = query.where(Meme.created_at < before)
    rows = session.execute(query.order_by(Meme.created_at.desc()).offset(offset).limit(limit))
    return [(m, topic) for m, topic in rows]


def detach_user(session: Session, user_id: str) -> None:
    """Khi xoá tài khoản: xoá meme và ảnh của người này, job và meme cũ được gỡ liên kết."""
    for m in session.scalars(select(Meme).where(Meme.user_id == user_id, Meme.deleted.is_(False))):
        m.deleted = True
        delete_meme_files(m)
    session.execute(update(Job).where(Job.user_id == user_id).values(user_id=None))
    session.execute(update(Meme).where(Meme.user_id == user_id).values(user_id=None))
