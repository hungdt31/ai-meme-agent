import base64
import hashlib
import hmac
import json
import time

from fastapi import Request

from app.config import get_settings


def client_ip(request: Request) -> str:
    # Cloud Run / Vercel đứng sau proxy: IP thật nằm đầu X-Forwarded-For
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def client_hash(request: Request) -> str:
    """Không lưu IP gốc, chỉ lưu hash có salt."""
    salt = get_settings().ip_hash_salt
    return hashlib.sha256(f"{salt}:{client_ip(request)}".encode()).hexdigest()


def sign_pair(meme_a: str, meme_b: str) -> str:
    payload = json.dumps({"a": meme_a, "b": meme_b, "t": time.time()}, separators=(",", ":")).encode()
    sig = hmac.new(get_settings().arena_hmac_secret.encode(), payload, hashlib.sha256).digest()
    return f"{_b64(payload)}.{_b64(sig)}"


def verify_pair(token: str, max_age_s: int = 3600) -> dict | None:
    try:
        payload_b64, sig_b64 = token.split(".")
        payload = _unb64(payload_b64)
        expected = hmac.new(get_settings().arena_hmac_secret.encode(), payload, hashlib.sha256).digest()
        if not hmac.compare_digest(expected, _unb64(sig_b64)):
            return None
        data = json.loads(payload)
    except (ValueError, json.JSONDecodeError):
        return None
    if time.time() - data["t"] > max_age_s:
        return None
    return data


def _b64(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).decode().rstrip("=")


def _unb64(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))
