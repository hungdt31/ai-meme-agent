from datetime import UTC, datetime

from app.core.errors import ApiError


def aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)  # SQLite trả datetime không múi giờ


def parse_before(before: str | None) -> datetime | None:
    """Cursor phân trang `before` (ISO 8601) của các danh sách sắp xếp theo thời gian."""
    if not before:
        return None
    try:
        return datetime.fromisoformat(before)
    except ValueError as e:
        raise ApiError(400, "invalid_input", "Tham số before không hợp lệ") from e
