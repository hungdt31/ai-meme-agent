"""Dependency FastAPI lấy người dùng hiện tại từ header Authorization: Bearer."""

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.auth import service
from app.auth.models import User
from app.core.db import get_session
from app.core.errors import ApiError


def bearer_token(request: Request) -> str | None:
    header = request.headers.get("authorization", "")
    if not header.lower().startswith("bearer "):
        return None
    return header[7:].strip() or None


def optional_user(request: Request, session: Session = Depends(get_session)) -> User | None:
    """Người dùng hiện tại, hoặc None nếu chưa đăng nhập. Token sai hay hết hạn cũng coi như khách."""
    token = bearer_token(request)
    return service.user_for_token(session, token) if token else None


def require_user(user: User | None = Depends(optional_user)) -> User:
    if user is None:
        raise ApiError(401, "unauthorized", "Bạn cần đăng nhập")
    return user
