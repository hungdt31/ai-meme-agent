import secrets
from collections.abc import Iterator
from datetime import UTC, datetime
from functools import lru_cache

from sqlalchemy import create_engine, inspect
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import get_settings


def new_id(n: int = 9) -> str:
    return secrets.token_urlsafe(n)[:12]


def now() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    pass


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
    import app.models  # noqa: F401 - đăng ký mọi bảng vào Base.metadata

    engine = engine or get_engine()
    Base.metadata.create_all(engine)
    check_schema(engine)


def get_session() -> Iterator[Session]:
    with get_sessionmaker()() as session:
        yield session
