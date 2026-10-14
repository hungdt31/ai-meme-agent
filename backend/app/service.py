"""Chạy job (stream sự kiện SSE) và lưu kết quả. Dùng cho API và các script."""

import asyncio
import logging
import time
from collections.abc import AsyncIterator

from sqlalchemy.orm import Session

from agent.graph import get_graph, initial_state
from agent.llm import LLMError
from agent.state import Candidate
from app.config import get_settings
from app.db import Job, Meme, User, get_sessionmaker, new_id
from app.storage import get_storage
from render.renderer import to_jpeg
from render.templates import UPLOAD_LAYOUTS, get_template

log = logging.getLogger(__name__)


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


def og_key(image_key: str) -> str:
    return image_key.rsplit(".", 1)[0] + ".jpg"


def save_meme_image(key: str, webp: bytes) -> None:
    storage = get_storage()
    storage.put(key, webp)
    storage.put(og_key(key), to_jpeg(webp), content_type="image/jpeg")


def delete_meme_files(m: Meme) -> None:
    storage = get_storage()
    storage.delete(m.image_key)
    storage.delete(og_key(m.image_key))


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


async def stream_job(job_id: str) -> AsyncIterator[dict]:
    settings = get_settings()
    with get_sessionmaker()() as session:
        job = session.get(Job, job_id)
        state = initial_state(job.id, job.topic, job.style, job.upload_key, job.template_id)
        final: dict | None = None
        started = time.monotonic()
        try:
            async with asyncio.timeout(settings.job_timeout_s):
                async for mode, chunk in get_graph().astream(state, stream_mode=["custom", "values"]):
                    if mode == "custom":
                        yield chunk
                    else:
                        final = chunk
        except (asyncio.CancelledError, GeneratorExit):
            # Trình duyệt đóng tab hoặc mất mạng giữa chừng: graph dừng theo, đánh dấu lỗi để job không treo ở running
            job.status, job.error = "failed", "client_disconnected"
            raise
        except TimeoutError:
            job.status, job.error = "failed", "timeout"
            yield {"type": "error", "code": "timeout", "message": "Chạy quá lâu, thử lại nhé"}
        except LLMError as e:
            log.warning("LLM error on job %s: %s", job_id, e)
            job.status, job.error = "failed", "llm_error"
            yield {"type": "error", "code": "llm_error", "message": "Gemini đang lỗi hoặc hết quota, thử lại sau"}
        except Exception:  # noqa: BLE001
            log.exception("job %s failed", job_id)
            job.status, job.error = "failed", "internal"
            yield {"type": "error", "code": "internal", "message": "Có lỗi xảy ra"}
        else:
            job.llm_calls = final.get("llm_calls", 0)
            winners = final.get("winners") or []
            if final.get("refusal") and not winners:
                job.status = "refused"
                yield {"type": "refused", "message": final["refusal"], "suggestions": final.get("suggestions", [])}
            else:
                desc = final.get("image_desc")
                memes = persist_winners(session, job, winners, desc.text_layout if desc else "top_bottom")
                job.status = "done"
                session.flush()
                owner = session.get(User, job.user_id) if job.user_id else None
                yield {"type": "result", "memes": [meme_out(m, owner) for m in memes]}
        finally:
            job.duration_ms = int((time.monotonic() - started) * 1000)
            session.commit()
        yield {"type": "done"}
