from datetime import datetime

from sqlalchemy import Boolean, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, new_id, now


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(16), primary_key=True, default=new_id)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    last_login_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    google_sub: Mapped[str] = mapped_column(String(64), unique=True)  # id ổn định của tài khoản Google
    email: Mapped[str] = mapped_column(String(320), unique=True)  # riêng tư, không bao giờ trả cho người khác
    display_name: Mapped[str] = mapped_column(String(60))
    avatar_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    username: Mapped[str] = mapped_column(String(20), unique=True)  # dùng cho /u/<username>
    profile_public: Mapped[bool] = mapped_column(Boolean, default=True)
    is_banned: Mapped[bool] = mapped_column(Boolean, default=False)


class AuthSession(Base):
    """Phiên đăng nhập. Chỉ lưu hash của token, lộ database cũng không dùng được token."""

    __tablename__ = "sessions"

    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(16), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
