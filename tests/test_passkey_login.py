from datetime import datetime, timezone

import pyotp
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.config import get_settings
from app.models.passkey import Passkey
from app.models.user import User
from tests.test_admin_api import _create_user, _login
from tests.webauthn_helpers import SoftAuthenticator


@pytest.fixture
def passkeys_enabled(monkeypatch):
    monkeypatch.setenv("WEBAUTHN_RP_ID", "localhost")
    monkeypatch.setenv("WEBAUTHN_ORIGIN", "http://localhost")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


async def _register_passkey(client, email="alice@example.com") -> SoftAuthenticator:
    """Sign in with a password, register a passkey, then sign out — ready to use it."""
    await _login(client, email)
    authenticator = SoftAuthenticator()
    options = (await client.post("/api/auth/passkeys/register/options")).json()
    resp = await client.post(
        "/api/auth/passkeys/register/verify", json={"credential": authenticator.register(options)}
    )
    assert resp.status_code == 200
    await client.post("/api/auth/logout")
    return authenticator


async def _login_options(client) -> dict:
    resp = await client.post("/api/auth/passkeys/login/options")
    assert resp.status_code == 200
    return resp.json()


async def _passkey_login(client, authenticator: SoftAuthenticator, **kwargs):
    options = await _login_options(client)
    return await client.post(
        "/api/auth/passkeys/login/verify", json={"credential": authenticator.assert_(options, **kwargs)}
    )


async def _only_passkey(test_engine) -> Passkey:
    maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with maker() as session:
        return (await session.execute(select(Passkey))).scalar_one()


async def test_login_options_are_public_and_discoverable(client, passkeys_enabled):
    options = await _login_options(client)
    assert options["rpId"] == "localhost"
    assert options["userVerification"] == "required"
    assert options["challenge"]
    # No allowCredentials: the browser offers whichever passkey it holds for this site.
    assert not options.get("allowCredentials")


async def test_passkey_login_is_unavailable_when_not_configured(client, monkeypatch):
    monkeypatch.setenv("WEBAUTHN_RP_ID", "")
    monkeypatch.setenv("WEBAUTHN_ORIGIN", "")
    get_settings.cache_clear()
    try:
        assert (await client.post("/api/auth/passkeys/login/options")).status_code == 404
        verify = await client.post("/api/auth/passkeys/login/verify", json={"credential": {}})
        assert verify.status_code == 404
    finally:
        get_settings.cache_clear()


async def test_signing_in_with_a_passkey(client, alice, passkeys_enabled):
    authenticator = await _register_passkey(client)

    resp = await _passkey_login(client, authenticator)
    assert resp.status_code == 200
    assert resp.json()["user"]["email"] == "alice@example.com"
    assert (await client.get("/api/auth/me")).json()["email"] == "alice@example.com"


async def test_passkey_login_skips_the_totp_step(client, alice, test_engine, passkeys_enabled):
    authenticator = await _register_passkey(client)

    maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with maker() as session:
        user = (await session.execute(select(User).where(User.id == alice.id))).scalar_one()
        user.totp_secret = pyotp.random_base32()
        user.is_2fa_enabled = True
        await session.commit()

    # The passkey is itself two factors (possession + biometric/PIN), so no code is asked for.
    resp = await _passkey_login(client, authenticator)
    assert resp.status_code == 200
    assert "requires_2fa" not in resp.json()
    assert (await client.get("/api/auth/me")).status_code == 200


async def test_successful_login_records_the_sign_count_and_use(client, alice, test_engine, passkeys_enabled):
    authenticator = await _register_passkey(client)
    await _passkey_login(client, authenticator)

    passkey = await _only_passkey(test_engine)
    assert passkey.sign_count == 1
    assert passkey.last_used_at is not None


async def test_unknown_credential_is_rejected(client, alice, passkeys_enabled):
    stranger = SoftAuthenticator()
    resp = await _passkey_login(client, stranger)
    assert resp.status_code == 400
    assert resp.json()["detail"] == "PASSKEY_LOGIN_FAILED"
    assert (await client.get("/api/auth/me")).status_code == 401


async def test_deactivated_member_cannot_sign_in_with_a_passkey(client, alice, test_engine, passkeys_enabled):
    bob = await _create_user(test_engine, "bob@example.com", "Bob")
    authenticator = await _register_passkey(client, "bob@example.com")
    maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with maker() as session:
        user = (await session.execute(select(User).where(User.id == bob.id))).scalar_one()
        user.is_active = False
        user.deactivated_at = datetime.now(timezone.utc)
        await session.commit()

    resp = await _passkey_login(client, authenticator)
    assert resp.status_code == 400
    assert (await client.get("/api/auth/me")).status_code == 401


async def test_assertion_for_another_origin_is_rejected(client, alice, passkeys_enabled):
    authenticator = await _register_passkey(client)
    resp = await _passkey_login(client, authenticator, origin="https://evil.example")
    assert resp.status_code == 400


async def test_assertion_without_user_verification_is_rejected(client, alice, passkeys_enabled):
    authenticator = await _register_passkey(client)
    resp = await _passkey_login(client, authenticator, user_verified=False)
    assert resp.status_code == 400


async def test_replayed_sign_count_is_rejected(client, alice, test_engine, passkeys_enabled):
    authenticator = await _register_passkey(client)
    assert (await _passkey_login(client, authenticator, sign_count=5)).status_code == 200
    await client.post("/api/auth/logout")

    # A cloned authenticator (or a replay) presents a counter that didn't advance.
    resp = await _passkey_login(client, authenticator, sign_count=3)
    assert resp.status_code == 400
    assert (await _only_passkey(test_engine)).sign_count == 5


async def test_assertion_without_a_fresh_challenge_is_rejected(client, alice, passkeys_enabled):
    authenticator = await _register_passkey(client)
    assertion = authenticator.assert_({"challenge": "AAAA"})
    resp = await client.post("/api/auth/passkeys/login/verify", json={"credential": assertion})
    assert resp.status_code == 400


async def test_a_challenge_can_only_be_used_once(client, alice, passkeys_enabled):
    authenticator = await _register_passkey(client)
    options = await _login_options(client)
    assertion = authenticator.assert_(options)

    first = await client.post("/api/auth/passkeys/login/verify", json={"credential": assertion})
    assert first.status_code == 200
    await client.post("/api/auth/logout")

    replay = await client.post("/api/auth/passkeys/login/verify", json={"credential": assertion})
    assert replay.status_code == 400


async def test_user_handle_must_belong_to_the_credentials_owner(client, alice, passkeys_enabled):
    authenticator = await _register_passkey(client)
    authenticator.user_handle = b"someone-elses-handle"
    resp = await _passkey_login(client, authenticator)
    assert resp.status_code == 400
    assert (await client.get("/api/auth/me")).status_code == 401


async def test_a_member_without_password_login_can_still_use_their_passkey(client, alice, test_engine, passkeys_enabled):
    authenticator = await _register_passkey(client)
    maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with maker() as session:
        user = (await session.execute(select(User).where(User.id == alice.id))).scalar_one()
        user.password_login_enabled = False
        await session.commit()

    assert (await _passkey_login(client, authenticator)).status_code == 200
