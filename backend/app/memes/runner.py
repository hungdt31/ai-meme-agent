"""Chạy agent LangGraph cho một job, chuyển sự kiện thành SSE và lưu meme thắng khi xong."""

import asyncio
import logging
import time
from collections.abc import AsyncIterator

from agent.graph import get_graph, initial_state
from agent.llm import LLMError
from app.auth.models import User
from app.core.config import get_settings
from app.core.db import get_sessionmaker
from app.memes.models import Job
from app.memes.schemas import MemeOut
from app.memes.service import persist_winners

log = logging.getLogger(__name__)


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
                yield {"type": "result", "memes": [MemeOut.of(m, owner).model_dump() for m in memes]}
        finally:
            job.duration_ms = int((time.monotonic() - started) * 1000)
            session.commit()
        yield {"type": "done"}
