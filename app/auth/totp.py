import base64
import json
import secrets
from datetime import datetime, timedelta, timezone
from io import BytesIO

import pyotp
import qrcode
from fastapi_users.password import PasswordHelper
from sqlalchemy import case, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User

_password_helper = PasswordHelper()

MAX_TOTP_ATTEMPTS = 5
TOTP_LOCKOUT_MINUTES = 15


def generate_totp_secret() -> str:
    return pyotp.random_base32()


def build_qr_data_uri(secret: str, email: str, issuer: str = "Breidablik") -> str:
    uri = pyotp.TOTP(secret).provisioning_uri(name=email, issuer_name=issuer)
    img = qrcode.make(uri)
    buffer = BytesIO()
    img.save(buffer, format="PNG")
    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def verify_totp_code(secret: str, code: str) -> bool:
    return pyotp.TOTP(secret).verify(code, valid_window=1)


def is_totp_locked(user: User) -> bool:
    if user.totp_locked_until is None:
        return False
    # Same defensive normalization as app/auth/device_trust.py:is_locked — SQLite (tests)
    # doesn't round-trip tzinfo through DateTime(timezone=True) the way Postgres does.
    locked_until = user.totp_locked_until
    if locked_until.tzinfo is None:
        locked_until = locked_until.replace(tzinfo=timezone.utc)
    return locked_until > datetime.now(timezone.utc)


async def register_totp_failure(session: AsyncSession, user: User) -> None:
    # Same atomic-UPDATE pattern as app/auth/device_trust.py:register_pin_failure and for the
    # same reason: a read-modify-write here would under-count a burst of concurrent guesses,
    # letting the lockout threshold never reliably trigger.
    new_attempts = User.totp_failed_attempts + 1
    await session.execute(
        update(User)
        .where(User.id == user.id)
        .values(
            totp_failed_attempts=new_attempts,
            totp_locked_until=case(
                (
                    new_attempts >= MAX_TOTP_ATTEMPTS,
                    datetime.now(timezone.utc) + timedelta(minutes=TOTP_LOCKOUT_MINUTES),
                ),
                else_=User.totp_locked_until,
            ),
        )
    )
    await session.commit()


async def register_totp_success(session: AsyncSession, user: User) -> None:
    user.totp_failed_attempts = 0
    user.totp_locked_until = None
    await session.commit()


def generate_recovery_codes(count: int = 8) -> list[str]:
    return [f"{secrets.token_hex(4)}-{secrets.token_hex(4)}" for _ in range(count)]


def hash_recovery_codes(codes: list[str]) -> str:
    return json.dumps([_password_helper.hash(code) for code in codes])


def verify_and_consume_recovery_code(code: str, hashed_codes_json: str | None) -> tuple[bool, str]:
    """Returns (matched, updated_hashed_codes_json). On a match, the used code is removed
    from the stored list so it can't be reused.
    """
    if not hashed_codes_json:
        return False, hashed_codes_json or "[]"

    hashed_codes: list[str] = json.loads(hashed_codes_json)
    for i, hashed in enumerate(hashed_codes):
        verified, _ = _password_helper.verify_and_update(code, hashed)
        if verified:
            remaining = hashed_codes[:i] + hashed_codes[i + 1 :]
            return True, json.dumps(remaining)
    return False, hashed_codes_json
