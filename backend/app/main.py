import logging
import warnings
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from slowapi.errors import RateLimitExceeded

from app.api import router
from app.core.config import get_settings
from app.core.db import init_db
from app.core.errors import ApiError
from app.core.limits import limiter
from app.social import router as social_router
from app.users_api import router as users_router
from render.templates import IMAGE_DIR

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
# Log mặc định của thư viện Google, không cần thiết
logging.getLogger("google_genai.models").setLevel(logging.WARNING)
warnings.filterwarnings("ignore", message=".*uses fixed sampling defaults.*")


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


def create_app() -> FastAPI:
    s = get_settings()
    app = FastAPI(title="Easy Meme API", version="0.1.0", lifespan=lifespan)
    app.state.limiter = limiter

    @app.exception_handler(ApiError)
    async def api_error(_: Request, exc: ApiError):
        return JSONResponse({"code": exc.code, "message": exc.message}, status_code=exc.status)

    @app.exception_handler(RateLimitExceeded)
    async def rate_limited(_: Request, exc: RateLimitExceeded):
        return JSONResponse(
            {"code": "rate_limited", "message": "Bạn đã dùng hết lượt hôm nay, quay lại mai nhé"}, status_code=429
        )

    @app.exception_handler(RequestValidationError)
    async def invalid(_: Request, exc: RequestValidationError):
        first = exc.errors()[0] if exc.errors() else {}
        field = ".".join(str(p) for p in first.get("loc", [])[1:])
        return JSONResponse(
            {"code": "invalid_input", "message": f"{field}: {first.get('msg', 'không hợp lệ')}"}, status_code=400
        )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=s.origins,
        allow_methods=["GET", "POST", "PATCH", "DELETE"],
        allow_headers=["Content-Type", "Authorization"],
    )
    app.include_router(router)
    app.include_router(users_router)
    app.include_router(social_router)
    if s.storage_backend == "local":
        Path(s.local_storage_dir).mkdir(parents=True, exist_ok=True)
        app.mount("/files", StaticFiles(directory=s.local_storage_dir), name="files")
    app.mount("/static/templates", StaticFiles(directory=IMAGE_DIR), name="templates")
    return app


app = create_app()
