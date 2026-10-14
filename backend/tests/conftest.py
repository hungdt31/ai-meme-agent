import os
import tempfile

# Cấu hình phải đặt trước khi import app: test luôn chạy FakeLLM, SQLite và thư mục tạm
_tmp = tempfile.mkdtemp(prefix="chememe-test-")
os.environ.update(
    {
        "LLM_FAKE": "1",
        "GOOGLE_API_KEY": "",
        "DATABASE_URL": f"sqlite:///{_tmp}/test.db",
        "STORAGE_BACKEND": "local",
        "LOCAL_STORAGE_DIR": f"{_tmp}/storage",
        "RATE_LIMIT_COMMENTS": "1000/hour",
        "RATE_LIMIT_POSTS": "1000/day",
        "QUOTA_ANON_PER_DAY": "1000",
        "QUOTA_USER_PER_DAY": "1000",
        "GOOGLE_CLIENT_ID": "test-client-id",
    }
)

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402


@pytest.fixture(scope="session")
def client():
    from app.main import app

    with TestClient(app) as c:
        yield c


@pytest.fixture
def login(client, monkeypatch):
    """Đăng nhập giả: thay bước xác thực token Google bằng claims cố định."""
    from app.auth import google

    def _login(sub: str = "google-sub-1", email: str = "lan@example.com", name: str = "Lan Nguyễn") -> dict:
        claims = {
            "sub": sub,
            "email": email,
            "name": name,
            "picture": "https://example.com/a.png",
            "email_verified": True,
            "iss": "accounts.google.com",
        }
        monkeypatch.setattr(google, "verify_google_credential", lambda credential: claims)
        data = client.post("/api/auth/google", json={"credential": "x" * 40}).json()
        return {"Authorization": f"Bearer {data['token']}", "user": data["user"]}

    return _login
