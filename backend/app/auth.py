"""Đăng nhập Google: frontend lấy ID token bằng Google Identity Services, backend xác thực rồi cấp token phiên riêng.

Token phiên gửi qua header Authorization: Bearer. Không dùng cookie vì frontend (Vercel) và backend (Cloud Run)
khác domain, trình duyệt chặn cookie bên thứ ba.
"""

import hashlib
import re
import secrets
from datetime import UTC, datetime, timedelta

from fastapi import Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import AuthSession, User, get_session
from app.errors import ApiError
from rag.search import fold

USERNAME_RE = re.compile(r"^[a-z0-9_]{3,20}$")


def verify_google_credential(credential: str) -> dict:
    """Kiểm tra chữ ký, hạn và audience của ID token Google. Test thay hàm này bằng monkeypatch."""
    from google.auth.transport import requests as google_requests
    from google.oauth2 import id_token

    client_id = get_settings().google_client_id
    if not client_id:
        raise ApiError(503, "auth_disabled", "Đăng nhập chưa được bật trên máy chủ")
    try:
        claims = id_token.verify_oauth2_token(credential, google_requests.Request(), client_id)
    except ValueError as e:
        raise ApiError(401, "invalid_credential", "Đăng nhập Google không hợp lệ, thử lại nhé") from e
    if claims.get("iss") not in ("accounts.google.com", "https://accounts.google.com"):
        raise ApiError(401, "invalid_credential", "Đăng nhập Google không hợp lệ")
    if not claims.get("email_verified"):
        raise ApiError(401, "email_unverified", "Email Google chưa được xác minh")
    return claims


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def suggest_username(session: Session, email: str, name: str) -> str:
    base = re.sub(r"[^a-z0-9_]", "", fold(email.split("@")[0]))[:15] or re.sub(r"[^a-z0-9_]", "", fold(name))[:15]
    if len(base) < 3:
        base = f"{base}user"[:7]
    candidate = base
    while session.scalar(select(User.id).where(User.username == candidate)):
        candidate = f"{base}{secrets.randbelow(10000)}"
    return candidate


def login_with_google(session: Session, claims: dict) -> tuple[User, str, datetime]:
    """Tạo hoặc cập nhật người dùng theo `sub` của Google, rồi cấp token phiên mới."""
    user = session.scalar(select(User).where(User.google_sub == claims["sub"]))
    now = datetime.now(UTC)
    if user is None:
        name = (claims.get("name") or claims["email"].split("@")[0])[:60]
        user = User(
            google_sub=claims["sub"],
            email=claims["email"],
            display_name=name,
            avatar_url=claims.get("picture"),
            username=suggest_username(session, claims["email"], name),
        )
        session.add(user)
    else:
        # Tên hiển thị người dùng có thể đã tự đổi, chỉ đồng bộ email và ảnh đại diện
        user.email = claims["email"]
        user.avatar_url = claims.get("picture") or user.avatar_url
        user.last_login_at = now
    if user.is_banned:
        raise ApiError(403, "banned", "Tài khoản đã bị khoá")
    token = secrets.token_urlsafe(32)
    expires = now + timedelta(days=get_settings().session_days)
    session.flush()
    session.add(AuthSession(token_hash=_hash(token), user_id=user.id, expires_at=expires))
    session.commit()
    return user, token, expires


def _bearer(request: Request) -> str | None:
    header = request.headers.get("authorization", "")
    if not header.lower().startswith("bearer "):
        return None
    return header[7:].strip() or None


def logout(session: Session, request: Request) -> None:
    token = _bearer(request)
    if token and (row := session.get(AuthSession, _hash(token))):
        session.delete(row)
        session.commit()


def optional_user(request: Request, session: Session = Depends(get_session)) -> User | None:
    """Người dùng hiện tại, hoặc None nếu chưa đăng nhập. Token sai hay hết hạn cũng coi như khách."""
    token = _bearer(request)
    if not token:
        return None
    row = session.get(AuthSession, _hash(token))
    if row is None:
        return None
    expires = row.expires_at if row.expires_at.tzinfo else row.expires_at.replace(tzinfo=UTC)  # SQLite bỏ múi giờ
    if expires < datetime.now(UTC):
        session.delete(row)
        session.commit()
        return None
    user = session.get(User, row.user_id)
    return None if user is None or user.is_banned else user


def require_user(user: User | None = Depends(optional_user)) -> User:
    if user is None:
        raise ApiError(401, "unauthorized", "Bạn cần đăng nhập")
    return user
