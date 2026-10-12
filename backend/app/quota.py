"""Lượt chế trong 24 giờ gần nhất, đếm trực tiếp trong bảng jobs.

Đếm bằng database (thay vì bộ nhớ như slowapi) nên đúng cả khi Cloud Run chạy nhiều instance.
Khách chưa đăng nhập được ít lượt hơn và tính theo hash IP.
"""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import Job, User


@dataclass
class Quota:
    limit: int
    used: int

    @property
    def left(self) -> int:
        return max(0, self.limit - self.used)

    def as_dict(self) -> dict:
        return {"limit": self.limit, "used": self.used, "left": self.left}


def get_quota(session: Session, user: User | None, client_hash: str) -> Quota:
    s = get_settings()
    since = datetime.now(UTC) - timedelta(days=1)
    query = select(func.count()).select_from(Job).where(Job.created_at >= since, Job.arena.is_(False))
    if user:
        return Quota(s.quota_user_per_day, session.scalar(query.where(Job.user_id == user.id)) or 0)
    used = session.scalar(query.where(Job.user_id.is_(None), Job.client_hash == client_hash)) or 0
    return Quota(s.quota_anon_per_day, used)
