"""In ra database mà backend sẽ dùng (theo backend/.env hoặc DATABASE_URL), che mật khẩu, kèm số dòng. Chỉ đọc.

Chạy từ backend/: .venv/bin/python ../.claude/skills/evals/scripts/db_target.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path.cwd()))
from sqlalchemy import inspect, text  # noqa: E402
from sqlalchemy.engine import make_url  # noqa: E402

from app.core.config import get_settings  # noqa: E402

url = make_url(get_settings().database_url)
print("Database:", url.render_as_string(hide_password=True))
if url.get_backend_name() == "sqlite" and url.database and not Path(url.database).exists():
    print("File SQLite chưa tồn tại (sẽ được tạo khi chạy).")  # không mở để tránh tạo file rỗng
    sys.exit(0)

from app.core.db import get_engine  # noqa: E402

engine = get_engine()
tables = set(inspect(engine).get_table_names())
with engine.connect() as conn:
    for table in ("jobs", "memes", "users", "posts", "comments"):
        if table in tables:
            print(f"  {table}: {conn.execute(text(f'SELECT COUNT(*) FROM {table}')).scalar()}")
