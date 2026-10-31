import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.config import get_settings
from app.models.user import DeviceTrust, User
from tests.test_admin_api import _login
from tests.test_passkey_login import _passkey_login, _register_passkey
from tests.webauthn_helpers import SoftAuthenticator

PASSWORD = "correcthorsebatterystaple"


@pytest.fixture
def passkeys_enabled(monkeypatch):
    monkeypatch.setenv("WEBAUTHN_RP_ID", "localhost")
    monkeypatch.setenv("WEBAUTHN_ORIGIN", "http://localhost")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


async def _set_password_login(client, enabled: bool):
    return await client.post("/api/auth/password-login", json={"enabled": enabled})


async def _reload(test_engine, user_id) -> User:
    maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with maker() as session:
        return (await session.execute(select(User).where(User.id == user_id))).scalar_one()


async def _register_while_signed_in(client) -> SoftAuthenticator:
    authenticator = SoftAuthenticator()
    options = (await client.post("/api/auth/passkeys/register/options")).json()
    resp = await client.post(
        "/api/auth/passkeys/register/verify", json={"credential": authenticator.register(options)}
    )
    assert resp.status_code == 200
    return authenticator


async def test_toggling_requires_login(client):
    assert (await _set_password_login(client, False)).status_code == 401


async def test_me_reports_the_setting(client, alice):
    await _login(client, "alice@example.com")
    assert (await client.get("/api/auth/me")).json()["password_login_enabled"] is True


async def test_cannot_turn_off_password_login_without_a_passkey(client, alice, test_engine, passkeys_enabled):
    await _login(client, "alice@example.com")
    resp = await _set_password_login(client, False)
    assert resp.status_code == 400
    assert resp.json()["detail"] == "NO_PASSKEY"
    assert (await _reload(test_engine, alice.id)).password_login_enabled is True


async def test_turning_off_password_login_with_a_passkey(client, alice, test_engine, passkeys_enabled):
    await _login(client, "alice@example.com")
    await _register_while_signed_in(client)

    resp = await _set_password_login(client, False)
    assert resp.status_code == 200
    assert (await _reload(test_engine, alice.id)).password_login_enabled is False
    assert (await client.get("/api/auth/me")).json()["password_login_enabled"] is False


async def test_password_login_is_refused_once_turned_off(client, alice, passkeys_enabled):
    await _login(client, "alice@example.com")
    await _register_while_signed_in(client)
    await _set_password_login(client, False)
    await client.post("/api/auth/logout")

    right = await client.post("/api/auth/login", json={"email": "alice@example.com", "password": PASSWORD})
    assert right.status_code == 403
    assert right.json()["detail"] == "PASSWORD_LOGIN_DISABLED"
    assert (await client.get("/api/auth/me")).status_code == 401

    # A wrong password is still just a bad login: nothing new is revealed without the secret.
    wrong = await client.post("/api/auth/login", json={"email": "alice@example.com", "password": "nope-nope-nope"})
    assert wrong.status_code == 400
    assert wrong.json()["detail"] == "LOGIN_BAD_CREDENTIALS"


async def test_pin_login_is_refused_once_turned_off(client, alice, test_engine, passkeys_enabled):
    await _login(client, "alice@example.com")
    await client.post("/api/auth/device-trust/enroll", json={"pin": "123456", "device_label": "Phone"})
    await client.post("/api/auth/logout")
    # Flip the flag directly so the device trust is still active: enforcement must not
    # depend on the trust having been revoked.
    maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with maker() as session:
        user = (await session.execute(select(User).where(User.id == alice.id))).scalar_one()
        user.password_login_enabled = False
        await session.commit()

    resp = await client.post("/api/auth/login/pin", json={"pin": "123456"})
    assert resp.status_code == 403
    assert resp.json()["detail"] == "PASSWORD_LOGIN_DISABLED"


async def test_turning_off_password_login_revokes_pin_shortcuts(client, alice, test_engine, passkeys_enabled):
    await _login(client, "alice@example.com")
    await client.post("/api/auth/device-trust/enroll", json={"pin": "123456", "device_label": "Phone"})
    await _register_while_signed_in(client)
    await _set_password_login(client, False)

    maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with maker() as session:
        trust = (await session.execute(select(DeviceTrust))).scalar_one()
    assert trust.revoked_at is not None


async def test_the_passkey_still_works_and_the_setting_can_be_reversed(client, alice, passkeys_enabled):
    await _login(client, "alice@example.com")
    authenticator = await _register_while_signed_in(client)
    await _set_password_login(client, False)
    await client.post("/api/auth/logout")

    assert (await _passkey_login(client, authenticator)).status_code == 200
    assert (await _set_password_login(client, True)).status_code == 200
    await client.post("/api/auth/logout")

    again = await client.post("/api/auth/login", json={"email": "alice@example.com", "password": PASSWORD})
    assert again.status_code == 200


async def test_turning_it_off_twice_is_harmless(client, alice, passkeys_enabled):
    await _login(client, "alice@example.com")
    await _register_while_signed_in(client)
    assert (await _set_password_login(client, False)).status_code == 200
    assert (await _set_password_login(client, False)).status_code == 200
