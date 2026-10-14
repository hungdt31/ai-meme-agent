from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]  # backend/


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Gemini
    google_api_key: str = ""
    gemini_model: str = "gemini-3.8-flash"
    # Chuỗi model dự phòng, phân cách bằng dấu phẩy, thử lần lượt khi model trước hết lượt, quá tải hay lỗi mạng.
    # Mỗi model có hạn mức free riêng. Để trống để tắt.
    gemini_fallback_model: str = "gemini-3.7-flash,gemini-3.6-flash,gemini-3.5-flash-lite,gemini-3.1-flash-lite"
    gemini_embed_model: str = "gemini-embedding-001"
    # Mức suy nghĩ: "low" nhanh hơn nhiều (đo được ~8 s thay vì ~25 s mỗi lần gọi với 3.8 Flash). Để trống = mặc định.
    gemini_reasoning_effort: Literal["minimal", "low", "medium", "high"] | None = "low"
    # Thời gian chờ tối đa mỗi lần gọi; quá thì chuyển sang model tiếp theo trong chuỗi
    gemini_timeout_s: float = 35
    # True = dùng FakeLLM (không gọi Gemini). Tự bật khi không có GOOGLE_API_KEY.
    llm_fake: bool = False

    # Database: SQLite khi chạy local, Postgres (Neon) khi deploy
    database_url: str = f"sqlite:///{BACKEND_DIR / 'chememe.db'}"

    # Lưu ảnh
    storage_backend: Literal["local", "r2"] = "local"
    local_storage_dir: str = str(BACKEND_DIR / "storage")
    public_base_url: str = "http://localhost:8000"
    r2_account_id: str = ""
    r2_access_key_id: str = ""
    r2_secret_access_key: str = ""
    r2_bucket: str = "chememe"
    r2_public_base_url: str = ""

    # Web
    allowed_origins: str = "http://localhost:3000"
    rate_limit_uploads: str = "30/day"
    rate_limit_rerender: str = "100/day"
    rate_limit_comments: str = "60/hour"
    rate_limit_posts: str = "30/day"

    # Đăng nhập Google: OAuth Client ID loại "Web application" (Google Cloud Console). Trống = tắt đăng nhập.
    google_client_id: str = ""
    session_days: int = 30
    # Lượt tạo mỗi 24 giờ, đếm trong database nên đúng cả khi chạy nhiều instance
    quota_user_per_day: int = 20
    quota_anon_per_day: int = 5

    # Bảo mật
    ip_hash_salt: str = "dev-salt-change-me"

    # Giới hạn
    max_topic_chars: int = 300
    max_caption_chars: int = 120
    max_upload_mb: int = 5
    max_upload_px: int = 4000
    job_timeout_s: int = 120
    max_rounds: int = 2  # số vòng viết caption tối đa (1 vòng đầu + 1 vòng viết lại)
    captions_per_template: int = 4
    report_hide_threshold: int = 3

    @property
    def use_fake_llm(self) -> bool:
        return self.llm_fake or not self.google_api_key

    @property
    def origins(self) -> list[str]:
        return [o.strip() for o in self.allowed_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
