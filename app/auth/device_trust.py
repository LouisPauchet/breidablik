import secrets
from datetime import datetime, timedelta, timezone

from fastapi_users.password import PasswordHelper
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import DeviceTrust

_password_helper = PasswordHelper()

MAX_PIN_ATTEMPTS = 5
LOCKOUT_MINUTES = 15
DEVICE_COOKIE_MAX_AGE = 60 * 60 * 24 * 180  # 180 days


def generate_device_id() -> str:
    return secrets.token_urlsafe(32)


def hash_pin(pin: str) -> str:
    return _password_helper.hash(pin)


async def get_active_device_trust(session: AsyncSession, device_id: str) -> DeviceTrust | None:
    result = await session.execute(
        select(DeviceTrust).where(
            DeviceTrust.device_id == device_id,
            DeviceTrust.revoked_at.is_(None),
        )
    )
    return result.scalar_one_or_none()


def is_locked(device: DeviceTrust) -> bool:
    if device.locked_until is None:
        return False
    # SQLite (used in tests) doesn't actually round-trip tzinfo through DateTime(timezone=True)
    # the way Postgres does, so a value read back here can come back naive even though it was
    # always written as UTC-aware — normalize defensively rather than assume the dialect kept it.
    locked_until = device.locked_until
    if locked_until.tzinfo is None:
        locked_until = locked_until.replace(tzinfo=timezone.utc)
    return locked_until > datetime.now(timezone.utc)


def verify_pin(pin: str, device: DeviceTrust) -> bool:
    verified, _ = _password_helper.verify_and_update(pin, device.pin_hash)
    return verified


async def register_pin_failure(session: AsyncSession, device: DeviceTrust) -> None:
    device.failed_pin_attempts += 1
    if device.failed_pin_attempts >= MAX_PIN_ATTEMPTS:
        device.locked_until = datetime.now(timezone.utc) + timedelta(minutes=LOCKOUT_MINUTES)
    await session.commit()


async def register_pin_success(session: AsyncSession, device: DeviceTrust) -> None:
    device.failed_pin_attempts = 0
    device.locked_until = None
    device.last_used_at = datetime.now(timezone.utc)
    await session.commit()


async def revoke_all_device_trusts(session: AsyncSession, user_id) -> None:
    await session.execute(
        update(DeviceTrust)
        .where(DeviceTrust.user_id == user_id, DeviceTrust.revoked_at.is_(None))
        .values(revoked_at=datetime.now(timezone.utc))
    )
    await session.commit()
