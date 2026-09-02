"""Custom auth endpoints for the pieces fastapi-users doesn't provide: a login that can pause
for a 2FA step, TOTP enrollment, and device-trust PIN quick-login. fastapi-users' own routers
(get_users_router) are mounted separately in app/main.py for the plain self-service/admin
CRUD they already cover well — this module only exists for the multi-step login flow they
don't support out of the box.
"""

import secrets
import uuid
from datetime import datetime, timezone
from types import SimpleNamespace

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi_users.authentication.strategy.db import DatabaseStrategy
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.backend import auth_backend, current_active_user
from app.auth.device_trust import (
    DEVICE_COOKIE_MAX_AGE,
    generate_device_id,
    get_active_device_trust,
    hash_pin,
    is_locked,
    register_pin_failure,
    register_pin_success,
    verify_pin,
)
from app.auth.tokens import make_token, read_token
from app.auth.totp import (
    build_qr_data_uri,
    generate_recovery_codes,
    generate_totp_secret,
    hash_recovery_codes,
    is_totp_locked,
    register_totp_failure,
    register_totp_success,
    verify_and_consume_recovery_code,
    verify_totp_code,
)
from app.auth.users import UserManager, get_user_manager
from app.config import get_settings
from app.db import get_session
from app.models.user import DeviceTrust, User
from app.schemas.auth import (
    ChangePasswordRequest,
    DeviceTrustEnrollRequest,
    InviteAcceptRequest,
    LoginRequest,
    PasswordConfirmRequest,
    PinLoginRequest,
    TotpEnrollConfirmRequest,
    TwoFactorVerifyRequest,
)
from app.schemas.user import UserUpdate

router = APIRouter(prefix="/api/auth", tags=["auth"])

PENDING_2FA_AUD = "breidablik:pending-2fa"
PENDING_TOTP_AUD = "breidablik:pending-totp-enroll"
PENDING_2FA_COOKIE = "pending_2fa"
PENDING_TOTP_COOKIE = "pending_totp"
DEVICE_ID_COOKIE = "device_id"
PENDING_LIFETIME_SECONDS = 300


def _serialize_user(user: User) -> dict:
    return {
        "id": str(user.id),
        "email": user.email,
        "display_name": user.display_name,
        "is_2fa_enabled": user.is_2fa_enabled,
        "is_superuser": user.is_superuser,
        "calendar_feed_token": user.calendar_feed_token,
        "birthday": user.birthday.isoformat() if user.birthday else None,
        "avatar_updated_at": user.avatar_updated_at.isoformat() if user.avatar_updated_at else None,
    }


def _cookie_kwargs(max_age: int) -> dict:
    settings = get_settings()
    return {
        "max_age": max_age,
        "httponly": True,
        "secure": settings.cookie_secure,
        "samesite": "lax",
    }


async def _finish_login(strategy: DatabaseStrategy, user: User) -> JSONResponse:
    login_response = await auth_backend.login(strategy, user)
    json_response = JSONResponse({"user": _serialize_user(user)})
    for header, value in login_response.headers.raw:
        if header == b"set-cookie":
            json_response.raw_headers.append((header, value))
    return json_response


@router.post("/login")
async def login(
    data: LoginRequest,
    user_manager: UserManager = Depends(get_user_manager),
    strategy: DatabaseStrategy = Depends(auth_backend.get_strategy),
):
    credentials = SimpleNamespace(username=data.email, password=data.password)
    user = await user_manager.authenticate(credentials)
    if user is None or not user.is_active:
        raise HTTPException(status_code=400, detail="LOGIN_BAD_CREDENTIALS")

    if user.is_2fa_enabled:
        token = make_token(PENDING_2FA_AUD, PENDING_LIFETIME_SECONDS, user_id=str(user.id))
        response = JSONResponse({"requires_2fa": True})
        response.set_cookie(PENDING_2FA_COOKIE, token, **_cookie_kwargs(PENDING_LIFETIME_SECONDS))
        return response

    return await _finish_login(strategy, user)


@router.post("/login/2fa")
async def login_2fa(
    data: TwoFactorVerifyRequest,
    request: Request,
    user_manager: UserManager = Depends(get_user_manager),
    strategy: DatabaseStrategy = Depends(auth_backend.get_strategy),
):
    token = request.cookies.get(PENDING_2FA_COOKIE)
    if not token:
        raise HTTPException(status_code=400, detail="NO_PENDING_2FA")
    try:
        payload = read_token(token, PENDING_2FA_AUD)
    except Exception as exc:
        raise HTTPException(status_code=400, detail="INVALID_OR_EXPIRED_TOKEN") from exc

    user = await user_manager.get(uuid.UUID(payload["user_id"]))
    session = user_manager.user_db.session

    if is_totp_locked(user):
        raise HTTPException(status_code=423, detail="2FA_LOCKED")

    ok = bool(user.totp_secret) and verify_totp_code(user.totp_secret, data.code)
    if not ok:
        matched, updated_codes = verify_and_consume_recovery_code(data.code, user.totp_recovery_codes)
        if matched:
            ok = True
            user.totp_recovery_codes = updated_codes
            await session.commit()

    if not ok:
        # Persistent per-user counter (not tied to the pending-2FA token) so an attacker who
        # already has the password can't reset their guess budget by just calling /login
        # again to mint a fresh pending token — see app/auth/totp.py.
        await register_totp_failure(session, user)
        raise HTTPException(status_code=400, detail="INVALID_CODE")

    await register_totp_success(session, user)

    response = await _finish_login(strategy, user)
    response.delete_cookie(PENDING_2FA_COOKIE)
    return response


@router.post("/login/pin")
async def login_pin(
    data: PinLoginRequest,
    request: Request,
    session: AsyncSession = Depends(get_session),
    user_manager: UserManager = Depends(get_user_manager),
    strategy: DatabaseStrategy = Depends(auth_backend.get_strategy),
):
    device_id = request.cookies.get(DEVICE_ID_COOKIE)
    device = await get_active_device_trust(session, device_id) if device_id else None
    if device is None:
        raise HTTPException(status_code=400, detail="NO_TRUSTED_DEVICE")
    if is_locked(device):
        raise HTTPException(status_code=423, detail="DEVICE_LOCKED")

    if not verify_pin(data.pin, device):
        await register_pin_failure(session, device)
        raise HTTPException(status_code=400, detail="INVALID_PIN")

    await register_pin_success(session, device)
    user = await user_manager.get(device.user_id)
    if user is None or not user.is_active:
        raise HTTPException(status_code=400, detail="LOGIN_BAD_CREDENTIALS")
    return await _finish_login(strategy, user)


@router.post("/logout")
async def logout(
    request: Request,
    user: User = Depends(current_active_user),
    strategy: DatabaseStrategy = Depends(auth_backend.get_strategy),
):
    token = request.cookies.get(auth_backend.transport.cookie_name)
    return await auth_backend.logout(strategy, user, token)


@router.get("/me")
async def me(user: User = Depends(current_active_user)):
    return _serialize_user(user)


@router.post("/calendar-feed/regenerate")
async def regenerate_calendar_feed_token(
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_session),
):
    """The token in /calendar/{token}.ics is a bearer credential fetched unauthenticated by
    external calendar apps — regenerate it here if it ever leaks, without touching the
    user's login credentials.
    """
    user.calendar_feed_token = secrets.token_urlsafe(32)
    await session.commit()
    return _serialize_user(user)


@router.get("/device-trust/status")
async def device_trust_status(
    request: Request,
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_session),
):
    """The device_id cookie is httpOnly (unreadable from JS by design), so the frontend
    can't tell on its own whether *this* device is already trusted — it has to ask.
    """
    device_id = request.cookies.get(DEVICE_ID_COOKIE)
    if not device_id:
        return {"trusted": False}
    device = await get_active_device_trust(session, device_id)
    if device is None or device.user_id != user.id:
        return {"trusted": False}
    return {"trusted": True, "device_label": device.device_label}


@router.post("/device-trust/enroll")
async def enroll_device_trust(
    data: DeviceTrustEnrollRequest,
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_session),
):
    """Only reachable from an already-authenticated session, which is what makes this safe:
    you must have completed one full login (password, plus 2FA if enabled) before you can
    set up a PIN shortcut for future logins on this device.
    """
    device_id = generate_device_id()
    session.add(
        DeviceTrust(
            user_id=user.id,
            device_id=device_id,
            device_label=data.device_label,
            pin_hash=hash_pin(data.pin),
        )
    )
    await session.commit()

    response = JSONResponse({"ok": True})
    response.set_cookie(DEVICE_ID_COOKIE, device_id, **_cookie_kwargs(DEVICE_COOKIE_MAX_AGE))
    return response


@router.post("/device-trust/revoke")
async def revoke_device_trust(
    request: Request,
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_session),
):
    device_id = request.cookies.get(DEVICE_ID_COOKIE)
    if device_id:
        device = await get_active_device_trust(session, device_id)
        if device and device.user_id == user.id:
            device.revoked_at = datetime.now(timezone.utc)
            await session.commit()
    response = JSONResponse({"ok": True})
    response.delete_cookie(DEVICE_ID_COOKIE)
    return response


@router.post("/2fa/enroll/start")
async def start_totp_enrollment(user: User = Depends(current_active_user)):
    if user.is_2fa_enabled:
        raise HTTPException(status_code=400, detail="2FA_ALREADY_ENABLED")

    secret = generate_totp_secret()
    token = make_token(PENDING_TOTP_AUD, PENDING_LIFETIME_SECONDS, user_id=str(user.id), secret=secret)
    qr_data_uri = build_qr_data_uri(secret, user.email)

    response = JSONResponse({"secret": secret, "qr_data_uri": qr_data_uri})
    response.set_cookie(PENDING_TOTP_COOKIE, token, **_cookie_kwargs(PENDING_LIFETIME_SECONDS))
    return response


@router.post("/2fa/enroll/confirm")
async def confirm_totp_enrollment(
    data: TotpEnrollConfirmRequest,
    request: Request,
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_session),
):
    token = request.cookies.get(PENDING_TOTP_COOKIE)
    if not token:
        raise HTTPException(status_code=400, detail="NO_PENDING_ENROLLMENT")
    try:
        payload = read_token(token, PENDING_TOTP_AUD)
    except Exception as exc:
        raise HTTPException(status_code=400, detail="INVALID_OR_EXPIRED_TOKEN") from exc
    if payload["user_id"] != str(user.id):
        raise HTTPException(status_code=400, detail="INVALID_OR_EXPIRED_TOKEN")

    secret = payload["secret"]
    if not verify_totp_code(secret, data.code):
        raise HTTPException(status_code=400, detail="INVALID_CODE")

    recovery_codes = generate_recovery_codes()
    user.totp_secret = secret
    user.is_2fa_enabled = True
    user.totp_recovery_codes = hash_recovery_codes(recovery_codes)
    await session.commit()

    response = JSONResponse({"recovery_codes": recovery_codes})
    response.delete_cookie(PENDING_TOTP_COOKIE)
    return response


@router.post("/2fa/disable")
async def disable_totp(
    data: PasswordConfirmRequest,
    user: User = Depends(current_active_user),
    user_manager: UserManager = Depends(get_user_manager),
    session: AsyncSession = Depends(get_session),
):
    credentials = SimpleNamespace(username=user.email, password=data.password)
    verified_user = await user_manager.authenticate(credentials)
    if verified_user is None:
        raise HTTPException(status_code=400, detail="INVALID_PASSWORD")

    user.is_2fa_enabled = False
    user.totp_secret = None
    user.totp_recovery_codes = None
    await session.commit()
    return {"ok": True}


@router.post("/change-password")
async def change_password(
    data: ChangePasswordRequest,
    request: Request,
    user: User = Depends(current_active_user),
    user_manager: UserManager = Depends(get_user_manager),
):
    """Requires the current password even though the request is already authenticated —
    same reasoning as disable_totp above: a session cookie alone shouldn't be enough to take
    over the account's credentials outright.
    """
    credentials = SimpleNamespace(username=user.email, password=data.current_password)
    verified_user = await user_manager.authenticate(credentials)
    if verified_user is None:
        raise HTTPException(status_code=400, detail="INVALID_CURRENT_PASSWORD")

    # UserManager.update's on_after_update hook revokes this device's PIN trust (and every
    # other device's), plus every other login session, since they were established under the
    # credential that just changed — passing `request` through lets it keep *this* session
    # (the one making this very request) logged in rather than immediately locking you out.
    await user_manager.update(UserUpdate(password=data.new_password), user, request=request)
    return {"ok": True}


async def _load_valid_invite(session: AsyncSession, token: str) -> User:
    result = await session.execute(select(User).where(User.invite_token == token))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=404, detail="INVITE_NOT_FOUND")

    expires_at = user.invite_token_expires_at
    if expires_at is not None and expires_at.tzinfo is None:
        # SQLite (tests) round-trips a DateTime(timezone=True) column back as naive; Postgres
        # (production) doesn't have this problem, but comparing safely costs nothing either way.
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at is None or expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=410, detail="INVITE_EXPIRED")
    return user


@router.get("/invite/{token}")
async def get_invite(token: str, session: AsyncSession = Depends(get_session)):
    user = await _load_valid_invite(session, token)
    return {"display_name": user.display_name, "email": user.email}


@router.post("/invite/{token}/accept")
async def accept_invite(
    token: str,
    data: InviteAcceptRequest,
    session: AsyncSession = Depends(get_session),
    user_manager: UserManager = Depends(get_user_manager),
    strategy: DatabaseStrategy = Depends(auth_backend.get_strategy),
):
    user = await _load_valid_invite(session, token)
    await user_manager.update(UserUpdate(password=data.password), user)

    user.is_active = True
    user.invite_token = None
    user.invite_token_expires_at = None
    await session.commit()
    await session.refresh(user)

    return await _finish_login(strategy, user)
