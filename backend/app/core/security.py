import hashlib

from fastapi import Request

from app.core.config import get_settings


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
