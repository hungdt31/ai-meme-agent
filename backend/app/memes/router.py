"""Tạo meme: ảnh tải lên, job (chạy agent qua SSE), sửa chữ, xoá, báo cáo, danh mục template và phong cách."""

import json

from fastapi import APIRouter, Depends, File, Request, UploadFile
from fastapi.responses import Response, StreamingResponse
from sqlalchemy.orm import Session

from agent.prompts import STYLES
from app.auth.deps import optional_user, require_user
from app.auth.models import User
from app.community.service import post_ids
from app.core.config import get_settings
from app.core.db import get_session
from app.core.limits import limiter
from app.core.security import client_hash
from app.memes import service
from app.memes.models import Job
from app.memes.runner import stream_job
from app.memes.schemas import CreateJob, Report, Rerender, meme_out
from render.templates import IMAGE_DIR, load_templates

router = APIRouter(prefix="/api")


def _owner(session: Session, user_id: str | None) -> User | None:
    return session.get(User, user_id) if user_id else None


# ---------- uploads ----------


@router.post("/uploads")
@limiter.limit(lambda: get_settings().rate_limit_uploads)
async def upload(request: Request, file: UploadFile = File(...)):
    data = await file.read(get_settings().max_upload_mb * 1024 * 1024 + 1)
    return {"upload_id": service.save_upload(data, file.content_type)}


# ---------- jobs ----------


@router.post("/jobs")
def create_job(
    request: Request,
    body: CreateJob,
    user: User | None = Depends(optional_user),
    session: Session = Depends(get_session),
):
    job = service.create_job(session, body, user, client_hash(request))
    return {"job_id": job.id}


@router.post("/jobs/{job_id}/run")
def run_job(job_id: str, session: Session = Depends(get_session)):
    service.start_job(session, job_id)

    async def events():
        async for event in stream_job(job_id):
            yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        events(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
    )


@router.get("/jobs/{job_id}")
def get_job(job_id: str, session: Session = Depends(get_session)):
    job = service.get_job(session, job_id)
    owner = _owner(session, job.user_id)
    return {
        "id": job.id,
        "status": job.status,
        "topic": job.topic,
        "style": job.style,
        "error": job.error,
        "memes": [meme_out(m, owner) for m in service.job_results(session, job_id)],
    }


# ---------- memes ----------


@router.get("/memes/{meme_id}")
def get_meme(meme_id: str, session: Session = Depends(get_session)):
    m = service.get_visible_meme(session, meme_id)
    job = session.get(Job, m.job_id)
    out = meme_out(m, _owner(session, m.user_id), post_id=post_ids(session, [m.id]).get(m.id))
    return out | {"topic": job.topic if job else None}


@router.post("/memes/{meme_id}/rerender")
@limiter.limit(lambda: get_settings().rate_limit_rerender)
def rerender(
    request: Request,
    meme_id: str,
    body: Rerender,
    user: User | None = Depends(optional_user),
    session: Session = Depends(get_session),
):
    m = service.get_visible_meme(session, meme_id)
    service.require_owner(m, user)
    new, result = service.rerender(session, m, body.captions)
    return meme_out(new, _owner(session, new.user_id)) | {
        "overflow": result.overflow,
        "overflow_boxes": result.overflow_boxes,
    }


@router.delete("/memes/{meme_id}", status_code=204)
def delete_meme(meme_id: str, user: User = Depends(require_user), session: Session = Depends(get_session)):
    service.delete_meme(session, meme_id, user)
    return Response(status_code=204)


@router.post("/memes/{meme_id}/report", status_code=204)
def report(meme_id: str, body: Report, session: Session = Depends(get_session)):
    service.report_meme(session, meme_id)
    return Response(status_code=204)


# ---------- danh mục ----------


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
