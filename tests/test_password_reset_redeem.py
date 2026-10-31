from datetime import datetime, timedelta, timezone

import pyotp
from fastapi_users.jwt import generate_jwt
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.auth.totp import hash_recovery_codes
from app.config import get_settings
from app.main import app
from app.models.user import DeviceTrust, User
from tests.test_admin_api import _create_user, _login

NEW_PASSWORD = "brandnewpassword"


async def _issue(client, user_id, **body) -> str:
    resp = await client.post(f"/api/admin/users/{user_id}/password-reset", json=body)
    assert resp.status_code == 200
    return resp.json()["token"]


async def _issue_as_admin(client, user_id, **body) -> str:
    """Log in as alice, mint the link, log out — the member redeems it unauthenticated."""
    await _login(client, "alice@example.com")
    token = await _issue(client, user_id, **body)
    await client.post("/api/auth/logout")
    return token


async def _enable_2fa(test_engine, user_id) -> str:
    secret = pyotp.random_base32()
    maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with maker() as session:
        user = (await session.execute(select(User).where(User.id == user_id))).scalar_one()
        user.totp_secret = secret
        user.is_2fa_enabled = True
        user.totp_recovery_codes = hash_recovery_codes(["abcd-efgh"])
        user.totp_failed_attempts = 3
        await session.commit()
    return secret


async def _reload(test_engine, user_id) -> User:
    maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with maker() as session:
        return (await session.execute(select(User).where(User.id == user_id))).scalar_one()


async def test_get_returns_name_and_email_for_a_valid_link(client, alice, test_engine):
    bob = await _create_user(test_engine, "bob@example.com", "Bob")
    token = await _issue_as_admin(client, bob.id)

    resp = await client.get(f"/api/auth/password-reset/{token}")
    assert resp.status_code == 200
    assert resp.json() == {"display_name": "Bob", "email": "bob@example.com"}


async def test_garbage_token_404s(client):
    assert (await client.get("/api/auth/password-reset/not-a-token")).status_code == 404
    post = await client.post("/api/auth/password-reset/not-a-token", json={"password": NEW_PASSWORD})
    assert post.status_code == 404


async def test_token_signed_with_another_secret_is_rejected(client, alice, test_engine):
    bob = await _create_user(test_engine, "bob@example.com", "Bob")
    forged = generate_jwt(
        {"sub": str(bob.id), "password_fgpt": "x", "aud": "fastapi-users:reset"}, "wrong-secret", 3600
    )
    assert (await client.get(f"/api/auth/password-reset/{forged}")).status_code == 404


async def test_expired_link_410s(client, alice, test_engine):
    bob = await _create_user(test_engine, "bob@example.com", "Bob")
    real = await _issue_as_admin(client, bob.id)
    # Re-sign the real token's claims with an expiry in the past.
    from fastapi_users.jwt import decode_jwt

    claims = decode_jwt(real, get_settings().secret_key, ["fastapi-users:reset"])
    claims.pop("exp")
    expired = generate_jwt(claims, get_settings().secret_key, -60)

    assert (await client.get(f"/api/auth/password-reset/{expired}")).status_code == 410
    post = await client.post(f"/api/auth/password-reset/{expired}", json={"password": NEW_PASSWORD})
    assert post.status_code == 410


async def test_redeeming_sets_the_new_password_and_logs_the_member_in(client, alice, test_engine):
    bob = await _create_user(test_engine, "bob@example.com", "Bob")
    token = await _issue_as_admin(client, bob.id)

    resp = await client.post(f"/api/auth/password-reset/{token}", json={"password": NEW_PASSWORD})
    assert resp.status_code == 200
    assert resp.json()["user"]["email"] == "bob@example.com"
    assert (await client.get("/api/auth/me")).json()["email"] == "bob@example.com"

    await client.post("/api/auth/logout")
    old = await client.post(
        "/api/auth/login", json={"email": "bob@example.com", "password": "correcthorsebatterystaple"}
    )
    assert old.status_code == 400
    new = await client.post("/api/auth/login", json={"email": "bob@example.com", "password": NEW_PASSWORD})
    assert new.status_code == 200


async def test_short_password_rejected(client, alice, test_engine):
    bob = await _create_user(test_engine, "bob@example.com", "Bob")
    token = await _issue_as_admin(client, bob.id)
    resp = await client.post(f"/api/auth/password-reset/{token}", json={"password": "short"})
    assert resp.status_code == 422


async def test_link_is_single_use(client, alice, test_engine):
    bob = await _create_user(test_engine, "bob@example.com", "Bob")
    token = await _issue_as_admin(client, bob.id)

    first = await client.post(f"/api/auth/password-reset/{token}", json={"password": NEW_PASSWORD})
    assert first.status_code == 200
    await client.post("/api/auth/logout")

    assert (await client.get(f"/api/auth/password-reset/{token}")).status_code == 404
    second = await client.post(f"/api/auth/password-reset/{token}", json={"password": "anotherpassword1"})
    assert second.status_code == 404


async def test_redeeming_revokes_other_sessions_and_trusted_devices(client, alice, test_engine):
    bob = await _create_user(test_engine, "bob@example.com", "Bob")
    maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with maker() as session:
        session.add(DeviceTrust(user_id=bob.id, device_id="dev-1", pin_hash="x"))
        await session.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as stale:
        await _login(stale, "bob@example.com")
        assert (await stale.get("/api/auth/me")).status_code == 200

        token = await _issue_as_admin(client, bob.id)
        await client.post(f"/api/auth/password-reset/{token}", json={"password": NEW_PASSWORD})

        # A session (or PIN shortcut) from before the reset is exactly what a reset is for.
        assert (await stale.get("/api/auth/me")).status_code == 401

    async with maker() as session:
        device = (await session.execute(select(DeviceTrust))).scalar_one()
    assert device.revoked_at is not None


async def test_member_with_2fa_still_needs_the_code_after_a_plain_reset(client, alice, test_engine):
    bob = await _create_user(test_engine, "bob@example.com", "Bob")
    secret = await _enable_2fa(test_engine, bob.id)
    token = await _issue_as_admin(client, bob.id)

    resp = await client.post(f"/api/auth/password-reset/{token}", json={"password": NEW_PASSWORD})
    assert resp.status_code == 200
    assert resp.json() == {"requires_2fa": True}
    # No session yet: the link alone must not bypass the second factor.
    assert (await client.get("/api/auth/me")).status_code == 401

    code = await client.post("/api/auth/login/2fa", json={"code": pyotp.TOTP(secret).now()})
    assert code.status_code == 200
    assert (await client.get("/api/auth/me")).status_code == 200


async def test_reset_2fa_link_clears_2fa_and_logs_in(client, alice, test_engine):
    bob = await _create_user(test_engine, "bob@example.com", "Bob")
    await _enable_2fa(test_engine, bob.id)
    token = await _issue_as_admin(client, bob.id, reset_2fa=True)

    resp = await client.post(f"/api/auth/password-reset/{token}", json={"password": NEW_PASSWORD})
    assert resp.status_code == 200
    assert resp.json()["user"]["is_2fa_enabled"] is False

    user = await _reload(test_engine, bob.id)
    assert user.is_2fa_enabled is False
    assert user.totp_secret is None
    assert user.totp_recovery_codes is None
    assert user.totp_failed_attempts == 0
    assert user.totp_locked_until is None


async def test_redeeming_re_enables_password_login(client, alice, test_engine):
    bob = await _create_user(test_engine, "bob@example.com", "Bob")
    maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with maker() as session:
        user = (await session.execute(select(User).where(User.id == bob.id))).scalar_one()
        user.password_login_enabled = False
        await session.commit()

    token = await _issue_as_admin(client, bob.id)
    await client.post(f"/api/auth/password-reset/{token}", json={"password": NEW_PASSWORD})

    assert (await _reload(test_engine, bob.id)).password_login_enabled is True


async def test_link_for_a_user_deactivated_after_issuing_is_rejected(client, alice, test_engine):
    bob = await _create_user(test_engine, "bob@example.com", "Bob")
    token = await _issue_as_admin(client, bob.id)

    maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with maker() as session:
        user = (await session.execute(select(User).where(User.id == bob.id))).scalar_one()
        user.is_active = False
        user.deactivated_at = datetime.now(timezone.utc) - timedelta(minutes=1)
        await session.commit()

    assert (await client.get(f"/api/auth/password-reset/{token}")).status_code == 404
    post = await client.post(f"/api/auth/password-reset/{token}", json={"password": NEW_PASSWORD})
    assert post.status_code == 404
