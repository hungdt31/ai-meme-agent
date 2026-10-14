"""Xác thực ID token do Google Identity Services cấp cho frontend."""

from app.core.config import get_settings
from app.core.errors import ApiError


def verify_google_credential(credential: str) -> dict:
    """Kiểm tra chữ ký, hạn và audience của ID token Google. Test thay hàm này bằng monkeypatch."""
    from google.auth.transport import requests as google_requests
    from google.oauth2 import id_token

    client_id = get_settings().google_client_id
    if not client_id:
        raise ApiError(503, "auth_disabled", "Đăng nhập chưa được bật trên máy chủ")
    try:
        claims = id_token.verify_oauth2_token(credential, google_requests.Request(), client_id)
    except ValueError as e:
        raise ApiError(401, "invalid_credential", "Đăng nhập Google không hợp lệ, thử lại nhé") from e
    if claims.get("iss") not in ("accounts.google.com", "https://accounts.google.com"):
        raise ApiError(401, "invalid_credential", "Đăng nhập Google không hợp lệ")
    if not claims.get("email_verified"):
        raise ApiError(401, "email_unverified", "Email Google chưa được xác minh")
    return claims
