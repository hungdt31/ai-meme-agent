from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, new_id, now


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(String(16), primary_key=True, default=new_id)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    input_type: Mapped[str] = mapped_column(String(16))  # topic | upload | template
    topic: Mapped[str | None] = mapped_column(Text, nullable=True)
    upload_key: Mapped[str | None] = mapped_column(String(128), nullable=True)
    template_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    style: Mapped[str | None] = mapped_column(String(32), nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="created")
    # created | running | done | refused | failed
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    client_hash: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    user_id: Mapped[str | None] = mapped_column(String(16), nullable=True, index=True)
    llm_calls: Mapped[int] = mapped_column(Integer, default=0)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Cột cũ của tính năng đấu trường (đã bỏ). Giữ vì database đã tạo có các cột này dạng NOT NULL.
    arena: Mapped[bool] = mapped_column(Boolean, default=False)
    variant: Mapped[str] = mapped_column(String(16), default="agent")


class Meme(Base):
    __tablename__ = "memes"

    id: Mapped[str] = mapped_column(String(16), primary_key=True, default=new_id)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    job_id: Mapped[str] = mapped_column(String(16), index=True)
    template_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    base_key: Mapped[str | None] = mapped_column(String(128), nullable=True)  # ảnh gốc khi tạo meme từ ảnh tải lên
    boxes: Mapped[list] = mapped_column(JSON, default=list)
    captions: Mapped[dict] = mapped_column(JSON, default=dict)
    image_key: Mapped[str] = mapped_column(String(128))
    scores: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    variant: Mapped[str] = mapped_column(String(16), default="agent")
    rank: Mapped[int | None] = mapped_column(Integer, nullable=True)
    parent_id: Mapped[str | None] = mapped_column(String(16), nullable=True)
    reported: Mapped[int] = mapped_column(Integer, default=0)
    hidden: Mapped[bool] = mapped_column(Boolean, default=False)  # ẩn do bị báo cáo
    user_id: Mapped[str | None] = mapped_column(String(16), nullable=True, index=True)  # chủ meme
    deleted: Mapped[bool] = mapped_column(Boolean, default=False)  # chủ meme đã xoá
