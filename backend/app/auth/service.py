"""Đăng nhập Google: frontend lấy ID token bằng Google Identity Services, backend xác thực rồi cấp token phiên riêng.

Token phiên gửi qua header Authorization: Bearer. Không dùng cookie vì frontend (Vercel) và backend (Cloud Run)
khác domain, trình duyệt chặn cookie bên thứ ba.
"""

import hashlib
import re
import secrets
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.models import AuthSession, User
from app.core.config import get_settings
from app.core.errors import ApiError
from rag.search import fold

USERNAME_RE = re.compile(r"^[a-z0-9_]{3,20}$")


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


def logout(session: Session, token: str | None) -> None:
    if token and (row := session.get(AuthSession, _hash(token))):
        session.delete(row)
        session.commit()


def user_for_token(session: Session, token: str) -> User | None:
    """Người dùng của token phiên. Token sai, hết hạn hoặc tài khoản bị khoá thì trả None."""
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


def end_all_sessions(session: Session, user_id: str) -> None:
    for row in session.scalars(select(AuthSession).where(AuthSession.user_id == user_id)):
        session.delete(row)
