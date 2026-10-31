"""Passkeys (WebAuthn): a member registers one or more from their profile, then can sign in
with it. Discoverable credentials with user verification are required throughout, so a passkey
is a complete two-factor sign-in on its own (the TOTP step is skipped for it — see login).
The challenge for each ceremony travels in a short-lived signed httpOnly cookie, which also
ties the ceremony to the browser that started it.
"""

import json
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from webauthn import (
    generate_registration_options,
    options_to_json,
    verify_registration_response,
)
from webauthn.helpers import base64url_to_bytes, bytes_to_base64url
from webauthn.helpers.structs import (
    AuthenticatorSelectionCriteria,
    PublicKeyCredentialDescriptor,
    ResidentKeyRequirement,
    UserVerificationRequirement,
)

from app.auth.backend import current_active_user
from app.auth.oauth import count_signin_methods
from app.auth.routes import cookie_kwargs
from app.auth.tokens import make_token, read_token
from app.config import Settings, get_settings
from app.db import get_session
from app.models.passkey import Passkey
from app.models.user import User

router = APIRouter(prefix="/api/auth/passkeys", tags=["passkeys"])

REGISTRATION_AUD = "breidablik:webauthn-registration"
REGISTRATION_COOKIE = "webauthn_registration"
CEREMONY_LIFETIME_SECONDS = 300


def require_passkeys_enabled() -> Settings:
    settings = get_settings()
    if not settings.webauthn_enabled:
        raise HTTPException(status_code=404, detail="PASSKEYS_NOT_ENABLED")
    return settings


class RegisterVerifyRequest(BaseModel):
    credential: dict
    label: str | None = Field(default=None, max_length=100)


def _serialize(passkey: Passkey) -> dict:
    return {
        "id": str(passkey.id),
        "label": passkey.label,
        "created_at": passkey.created_at.isoformat() if passkey.created_at else None,
        "last_used_at": passkey.last_used_at.isoformat() if passkey.last_used_at else None,
    }


@router.get("/config")
async def passkey_config() -> dict:
    return {"enabled": get_settings().webauthn_enabled}


@router.post("/register/options")
async def registration_options(
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(require_passkeys_enabled),
):
    existing = await session.execute(select(Passkey.credential_id).where(Passkey.user_id == user.id))
    options = generate_registration_options(
        rp_id=settings.webauthn_effective_rp_id,
        rp_name=settings.webauthn_rp_name,
        user_id=user.id.bytes,
        user_name=user.email,
        user_display_name=user.display_name,
        authenticator_selection=AuthenticatorSelectionCriteria(
            resident_key=ResidentKeyRequirement.REQUIRED,
            user_verification=UserVerificationRequirement.REQUIRED,
        ),
        exclude_credentials=[
            PublicKeyCredentialDescriptor(id=base64url_to_bytes(cid)) for cid in existing.scalars()
        ],
    )

    token = make_token(
        REGISTRATION_AUD,
        CEREMONY_LIFETIME_SECONDS,
        user_id=str(user.id),
        challenge=bytes_to_base64url(options.challenge),
    )
    response = JSONResponse(json.loads(options_to_json(options)))
    response.set_cookie(REGISTRATION_COOKIE, token, **cookie_kwargs(CEREMONY_LIFETIME_SECONDS))
    return response


@router.post("/register/verify")
async def verify_registration(
    data: RegisterVerifyRequest,
    request: Request,
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(require_passkeys_enabled),
):
    failed = HTTPException(status_code=400, detail="PASSKEY_REGISTRATION_FAILED")
    token = request.cookies.get(REGISTRATION_COOKIE)
    if not token:
        raise failed
    try:
        claims = read_token(token, REGISTRATION_AUD)
    except Exception as exc:
        raise failed from exc
    if claims.get("user_id") != str(user.id):
        raise failed

    try:
        verified = verify_registration_response(
            credential=data.credential,
            expected_challenge=base64url_to_bytes(claims["challenge"]),
            expected_rp_id=settings.webauthn_effective_rp_id,
            expected_origin=settings.webauthn_origin,
            require_user_verification=True,
        )
    except Exception as exc:
        raise failed from exc

    passkey = Passkey(
        user_id=user.id,
        credential_id=bytes_to_base64url(verified.credential_id),
        public_key=verified.credential_public_key,
        sign_count=verified.sign_count,
        label=data.label,
    )
    session.add(passkey)
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise failed from exc

    response = JSONResponse(_serialize(passkey))
    response.delete_cookie(REGISTRATION_COOKIE)
    return response


@router.get("")
async def list_passkeys(
    user: User = Depends(current_active_user), session: AsyncSession = Depends(get_session)
):
    result = await session.execute(
        select(Passkey).where(Passkey.user_id == user.id).order_by(Passkey.created_at, Passkey.id)
    )
    return [_serialize(p) for p in result.scalars()]


@router.delete("/{passkey_id}")
async def delete_passkey(
    passkey_id: uuid.UUID,
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(
        select(Passkey).where(Passkey.id == passkey_id, Passkey.user_id == user.id)
    )
    passkey = result.scalar_one_or_none()
    if passkey is None:
        raise HTTPException(status_code=404, detail="PASSKEY_NOT_FOUND")

    if await count_signin_methods(session, user, excluding_passkey_id=passkey.id) == 0:
        raise HTTPException(status_code=400, detail="LAST_SIGNIN_METHOD")

    await session.delete(passkey)
    await session.commit()
    return {"ok": True}
