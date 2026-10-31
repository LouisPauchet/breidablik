import uuid

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


async def _options(client) -> dict:
    resp = await client.post("/api/auth/passkeys/register/options")
    assert resp.status_code == 200
    return resp.json()


async def _register(client, authenticator: SoftAuthenticator, label: str | None = "Laptop", **kwargs):
    options = await _options(client)
    credential = authenticator.register(options, **kwargs)
    return await client.post(
        "/api/auth/passkeys/register/verify", json={"credential": credential, "label": label}
    )


async def _passkeys(test_engine) -> list[Passkey]:
    maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with maker() as session:
        return list((await session.execute(select(Passkey))).scalars())


async def test_config_reports_passkeys_disabled_when_unconfigured(client, monkeypatch):
    monkeypatch.setenv("WEBAUTHN_RP_ID", "")
    monkeypatch.setenv("WEBAUTHN_ORIGIN", "")
    get_settings.cache_clear()
    try:
        assert (await client.get("/api/auth/passkeys/config")).json() == {"enabled": False}
    finally:
        get_settings.cache_clear()


async def test_config_reports_passkeys_enabled_when_configured(client, passkeys_enabled):
    assert (await client.get("/api/auth/passkeys/config")).json() == {"enabled": True}


async def test_rp_id_defaults_to_the_origins_hostname(client, monkeypatch):
    monkeypatch.setenv("WEBAUTHN_RP_ID", "")
    monkeypatch.setenv("WEBAUTHN_ORIGIN", "https://home.example.org")
    get_settings.cache_clear()
    try:
        assert get_settings().webauthn_effective_rp_id == "home.example.org"
    finally:
        get_settings.cache_clear()


async def test_registration_requires_login(client, passkeys_enabled):
    assert (await client.post("/api/auth/passkeys/register/options")).status_code == 401


async def test_registration_is_unavailable_when_not_configured(client, alice, monkeypatch):
    monkeypatch.setenv("WEBAUTHN_RP_ID", "")
    monkeypatch.setenv("WEBAUTHN_ORIGIN", "")
    get_settings.cache_clear()
    try:
        await _login(client, "alice@example.com")
        assert (await client.post("/api/auth/passkeys/register/options")).status_code == 404
    finally:
        get_settings.cache_clear()


async def test_options_demand_a_discoverable_user_verified_credential(client, alice, passkeys_enabled):
    await _login(client, "alice@example.com")
    options = await _options(client)

    assert options["rp"]["id"] == "localhost"
    assert options["challenge"]
    selection = options["authenticatorSelection"]
    assert selection["residentKey"] == "required"
    assert selection["userVerification"] == "required"


async def test_registering_a_passkey_stores_it(client, alice, test_engine, passkeys_enabled):
    await _login(client, "alice@example.com")
    authenticator = SoftAuthenticator()

    resp = await _register(client, authenticator, "Laptop")
    assert resp.status_code == 200
    assert resp.json()["label"] == "Laptop"

    [passkey] = await _passkeys(test_engine)
    assert passkey.user_id == alice.id
    assert passkey.credential_id == authenticator.credential_id_b64
    assert passkey.label == "Laptop"
    assert passkey.sign_count == 0
    assert passkey.public_key

    listing = (await client.get("/api/auth/passkeys")).json()
    assert [(p["id"], p["label"]) for p in listing] == [(str(passkey.id), "Laptop")]


async def test_already_registered_credentials_are_excluded_from_new_options(client, alice, passkeys_enabled):
    await _login(client, "alice@example.com")
    authenticator = SoftAuthenticator()
    await _register(client, authenticator)

    options = await _options(client)
    assert [c["id"] for c in options["excludeCredentials"]] == [authenticator.credential_id_b64]


async def test_verify_without_fresh_options_is_rejected(client, alice, test_engine, passkeys_enabled):
    await _login(client, "alice@example.com")
    credential = SoftAuthenticator().register(
        {"challenge": "AAAA", "user": {"id": "AAAA"}}
    )
    resp = await client.post("/api/auth/passkeys/register/verify", json={"credential": credential})
    assert resp.status_code == 400
    assert await _passkeys(test_engine) == []


async def test_wrong_origin_is_rejected(client, alice, test_engine, passkeys_enabled):
    await _login(client, "alice@example.com")
    resp = await _register(client, SoftAuthenticator(), origin="https://evil.example")
    assert resp.status_code == 400
    assert resp.json()["detail"] == "PASSKEY_REGISTRATION_FAILED"
    assert await _passkeys(test_engine) == []


async def test_authenticator_without_user_verification_is_rejected(client, alice, test_engine, passkeys_enabled):
    await _login(client, "alice@example.com")
    resp = await _register(client, SoftAuthenticator(), user_verified=False)
    assert resp.status_code == 400
    assert await _passkeys(test_engine) == []


async def test_challenge_issued_to_one_member_cannot_register_for_another(client, alice, test_engine, passkeys_enabled):
    await _create_user(test_engine, "bob@example.com", "Bob")
    await _login(client, "alice@example.com")
    options = await _options(client)  # sets alice's challenge cookie in this browser
    await client.post("/api/auth/logout")

    await _login(client, "bob@example.com")
    credential = SoftAuthenticator().register(options)
    resp = await client.post("/api/auth/passkeys/register/verify", json={"credential": credential})
    assert resp.status_code == 400
    assert await _passkeys(test_engine) == []


async def test_the_same_credential_cannot_be_registered_twice(client, alice, test_engine, passkeys_enabled):
    await _login(client, "alice@example.com")
    authenticator = SoftAuthenticator()
    assert (await _register(client, authenticator)).status_code == 200
    # Fresh options (the exclude list would stop a real browser; a hostile client ignores it).
    again = await _register(client, authenticator)
    assert again.status_code == 400
    assert len(await _passkeys(test_engine)) == 1


async def test_listing_requires_login_and_shows_only_your_own(client, alice, test_engine, passkeys_enabled):
    bob = await _create_user(test_engine, "bob@example.com", "Bob")
    maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with maker() as session:
        session.add(Passkey(user_id=bob.id, credential_id="bobs-cred", public_key=b"x", sign_count=0))
        await session.commit()

    assert (await client.get("/api/auth/passkeys")).status_code == 401
    await _login(client, "alice@example.com")
    assert (await client.get("/api/auth/passkeys")).json() == []


async def test_deleting_a_passkey(client, alice, test_engine, passkeys_enabled):
    await _login(client, "alice@example.com")
    await _register(client, SoftAuthenticator())
    [passkey] = await _passkeys(test_engine)

    assert (await client.delete(f"/api/auth/passkeys/{passkey.id}")).status_code == 200
    assert await _passkeys(test_engine) == []
    assert (await client.delete(f"/api/auth/passkeys/{passkey.id}")).status_code == 404


async def test_cannot_delete_someone_elses_passkey(client, alice, test_engine, passkeys_enabled):
    bob = await _create_user(test_engine, "bob@example.com", "Bob")
    maker = async_sessionmaker(test_engine, expire_on_commit=False)
    other_id = uuid.uuid4()
    async with maker() as session:
        session.add(Passkey(id=other_id, user_id=bob.id, credential_id="bobs-cred", public_key=b"x", sign_count=0))
        await session.commit()

    await _login(client, "alice@example.com")
    assert (await client.delete(f"/api/auth/passkeys/{other_id}")).status_code == 404
    assert len(await _passkeys(test_engine)) == 1


async def test_cannot_delete_the_last_way_to_sign_in(client, alice, test_engine, passkeys_enabled):
    await _login(client, "alice@example.com")
    await _register(client, SoftAuthenticator())
    maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with maker() as session:
        user = (await session.execute(select(User).where(User.id == alice.id))).scalar_one()
        user.password_login_enabled = False
        await session.commit()

    [passkey] = await _passkeys(test_engine)
    resp = await client.delete(f"/api/auth/passkeys/{passkey.id}")
    assert resp.status_code == 400
    assert resp.json()["detail"] == "LAST_SIGNIN_METHOD"
    assert len(await _passkeys(test_engine)) == 1


async def test_can_delete_one_of_two_passkeys_without_a_password(client, alice, test_engine, passkeys_enabled):
    await _login(client, "alice@example.com")
    await _register(client, SoftAuthenticator(), "One")
    await _register(client, SoftAuthenticator(), "Two")
    maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with maker() as session:
        user = (await session.execute(select(User).where(User.id == alice.id))).scalar_one()
        user.password_login_enabled = False
        await session.commit()

    first, second = await _passkeys(test_engine)
    assert (await client.delete(f"/api/auth/passkeys/{first.id}")).status_code == 200
    assert (await client.delete(f"/api/auth/passkeys/{second.id}")).status_code == 400
