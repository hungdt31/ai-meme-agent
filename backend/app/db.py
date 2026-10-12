import secrets
from collections.abc import Iterator
from datetime import UTC, datetime
from functools import lru_cache

from sqlalchemy import JSON, Boolean, DateTime, Index, Integer, String, Text, create_engine, inspect
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

from app.config import get_settings


def new_id(n: int = 9) -> str:
    return secrets.token_urlsafe(n)[:12]


def now() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    pass


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
    # Đấu trường: job sinh sẵn theo bộ chủ đề cố định
    arena: Mapped[bool] = mapped_column(Boolean, default=False)
    variant: Mapped[str] = mapped_column(String(16), default="agent")  # agent | baseline


class Meme(Base):
    __tablename__ = "memes"

    id: Mapped[str] = mapped_column(String(16), primary_key=True, default=new_id)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    job_id: Mapped[str] = mapped_column(String(16), index=True)
    template_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    base_key: Mapped[str | None] = mapped_column(String(128), nullable=True)  # ảnh gốc khi chế ảnh tải lên
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


class Vote(Base):
    __tablename__ = "votes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    meme_a: Mapped[str] = mapped_column(String(16))
    meme_b: Mapped[str] = mapped_column(String(16))
    winner: Mapped[str] = mapped_column(String(8))  # a | b | tie
    client_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    user_id: Mapped[str | None] = mapped_column(String(16), nullable=True)
    pair_key: Mapped[str | None] = mapped_column(String(40), nullable=True)  # "<id nhỏ>|<id lớn>"

    # Mỗi người chỉ có một phiếu cho mỗi cặp; phiếu ẩn danh (user_id NULL) không bị ràng buộc
    __table_args__ = (Index("uq_votes_user_pair", "user_id", "pair_key", unique=True),)


def pair_key(a: str, b: str) -> str:
    return "|".join(sorted((a, b)))


@lru_cache
def get_engine() -> Engine:
    url = get_settings().database_url
    # Neon cho chuỗi "postgresql://", SQLAlchemy cần driver psycopg 3
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+psycopg://", 1)
    kwargs = {"connect_args": {"check_same_thread": False}} if url.startswith("sqlite") else {"pool_pre_ping": True}
    return create_engine(url, **kwargs)


@lru_cache
def get_sessionmaker() -> sessionmaker[Session]:
    return sessionmaker(bind=get_engine(), expire_on_commit=False)


class SchemaOutdated(RuntimeError):
    pass


def check_schema(engine: Engine) -> None:
    """create_all chỉ tạo bảng còn thiếu, không thêm cột vào bảng đã có. Báo rõ khi database tạo từ phiên bản cũ."""
    insp = inspect(engine)
    existing = set(insp.get_table_names())
    missing = []
    for table in Base.metadata.sorted_tables:
        if table.name in existing:
            cols = {c["name"] for c in insp.get_columns(table.name)}
            missing += [f"{table.name}.{c.name}" for c in table.columns if c.name not in cols]
    if missing:
        raise SchemaOutdated(
            f"Database thiếu cột {', '.join(missing)} (tạo từ phiên bản cũ). "
            "Xoá các bảng cũ hoặc dùng database mới, backend sẽ tự tạo lại bảng khi khởi động."
        )


def init_db(engine: Engine | None = None) -> None:
    engine = engine or get_engine()
    Base.metadata.create_all(engine)
    check_schema(engine)


def get_session() -> Iterator[Session]:
    with get_sessionmaker()() as session:
        yield session
