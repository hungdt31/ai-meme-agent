"""Đăng nhập, tài khoản của tôi, lịch sử meme và hồ sơ công khai."""

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.auth import google
from app.auth import service as auth
from app.auth.deps import bearer_token, optional_user, require_user
from app.auth.models import User
from app.core.db import get_session
from app.core.limits import limiter
from app.core.security import client_hash
from app.core.time import parse_before
from app.memes.quota import get_quota
from app.users import service
from app.users.schemas import GoogleLogin, GuestQuotaOut, LoginOut, MemePage, MeOut, PublicProfileOut, UpdateMe

router = APIRouter(prefix="/api")


# ---------- đăng nhập ----------


@router.post("/auth/google", response_model=LoginOut)
@limiter.limit("30/hour")
def google_login(request: Request, body: GoogleLogin, session: Session = Depends(get_session)):
    claims = google.verify_google_credential(body.credential)
    user, token, expires = auth.login_with_google(session, claims)
    return LoginOut(
        token=token, expires_at=expires.isoformat(), user=service.me_out(session, user, client_hash(request))
    )


@router.post("/auth/logout", status_code=204)
def logout(request: Request, session: Session = Depends(get_session)):
    auth.logout(session, bearer_token(request))
    return Response(status_code=204)


# ---------- tài khoản của tôi ----------


@router.get("/me", response_model=MeOut)
def get_me(request: Request, user: User = Depends(require_user), session: Session = Depends(get_session)):
    return service.me_out(session, user, client_hash(request))


@router.get("/me/quota", response_model=GuestQuotaOut)
def my_quota(request: Request, user: User | None = Depends(optional_user), session: Session = Depends(get_session)):
    """Dùng cho cả khách: hiện số lượt còn lại trên form."""
    return GuestQuotaOut(**get_quota(session, user, client_hash(request)).as_dict(), signed_in=user is not None)


@router.patch("/me", response_model=MeOut)
def update_me(
    request: Request, body: UpdateMe, user: User = Depends(require_user), session: Session = Depends(get_session)
):
    service.update_profile(session, user, body)
    return service.me_out(session, user, client_hash(request))


@router.delete("/me", status_code=204)
def delete_me(user: User = Depends(require_user), session: Session = Depends(get_session)):
    service.delete_account(session, user)
    return Response(status_code=204)


@router.get("/me/memes", response_model=MemePage)
def my_memes(
    page: int = Query(1, ge=1),
    page_size: int = Query(12, ge=1, le=48),
    user: User = Depends(require_user),
    session: Session = Depends(get_session),
):
    return service.my_memes(session, user, page, page_size)


# ---------- hồ sơ công khai ----------


@router.get("/users/{username}", response_model=PublicProfileOut)
def public_profile(username: str, before: str | None = None, session: Session = Depends(get_session)):
    return service.public_profile(session, username, parse_before(before))
