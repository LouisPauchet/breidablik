from urllib.parse import parse_qs, urlparse

import pyotp
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.main import app
from app.models.oauth import OAuthAccount
from app.models.user import User
from tests.test_admin_api import _create_user
from tests.test_oauth_linking import FakeOAuthClient, fake_providers  # noqa: F401  (fixture)


async def _link(test_engine, user_id, provider="google", account_id="google-id-1"):
    maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with maker() as session:
        session.add(OAuthAccount(user_id=user_id, provider=provider, account_id=account_id))
        await session.commit()


async def _begin_login(client, provider="google"):
    resp = await client.get(f"/api/auth/oauth/{provider}/login")
    assert resp.status_code == 302
    state = parse_qs(urlparse(resp.headers["location"]).query)["state"][0]
    return resp, state


async def _callback(client, state, provider="google", code="abc"):
    return await client.get(f"/api/auth/oauth/{provider}/callback?code={code}&state={state}")


async def test_login_start_redirects_to_the_provider_and_sets_a_nonce_cookie(client, fake_providers):
    resp, state = await _begin_login(client)
    assert resp.headers["location"].startswith("https://provider.example/authorize")
    assert state
    assert "oauth_nonce" in resp.headers.get("set-cookie", "")


async def test_login_start_404s_for_an_unconfigured_provider(client, fake_providers):
    assert (await client.get("/api/auth/oauth/microsoft/login")).status_code == 404


async def test_linked_account_signs_in(client, alice, test_engine, fake_providers):
    await _link(test_engine, alice.id)
    _, state = await _begin_login(client)

    resp = await _callback(client, state)
    assert resp.status_code == 302
    assert resp.headers["location"] == "/"

    me = await client.get("/api/auth/me")
    assert me.status_code == 200
    assert me.json()["email"] == "alice@example.com"


async def test_unlinked_identity_does_not_sign_in_and_creates_no_user(client, alice, test_engine, fake_providers):
    # The provider identity is valid, but nobody linked it — and its email matching
    # alice's must not be treated as proof it is hers.
    fake_providers["google"] = FakeOAuthClient("someone-else", "alice@example.com")
    _, state = await _begin_login(client)

    resp = await _callback(client, state)
    assert resp.headers["location"] == "/login?oauth=unlinked"
    assert (await client.get("/api/auth/me")).status_code == 401

    maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with maker() as session:
        assert len((await session.execute(select(User))).scalars().all()) == 1


async def test_deactivated_member_cannot_sign_in_with_a_linked_account(client, alice, test_engine, fake_providers):
    bob = await _create_user(test_engine, "bob@example.com", "Bob")
    await _link(test_engine, bob.id)
    maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with maker() as session:
        user = (await session.execute(select(User).where(User.id == bob.id))).scalar_one()
        user.is_active = False
        await session.commit()

    _, state = await _begin_login(client)
    resp = await _callback(client, state)
    assert resp.headers["location"] == "/login?oauth=error"
    assert (await client.get("/api/auth/me")).status_code == 401


async def test_member_with_2fa_still_has_to_enter_the_code(client, alice, test_engine, fake_providers):
    secret = pyotp.random_base32()
    maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with maker() as session:
        user = (await session.execute(select(User).where(User.id == alice.id))).scalar_one()
        user.totp_secret = secret
        user.is_2fa_enabled = True
        await session.commit()
    await _link(test_engine, alice.id)

    _, state = await _begin_login(client)
    resp = await _callback(client, state)
    assert resp.headers["location"] == "/login?oauth=2fa"
    assert (await client.get("/api/auth/me")).status_code == 401

    code = await client.post("/api/auth/login/2fa", json={"code": pyotp.TOTP(secret).now()})
    assert code.status_code == 200
    assert (await client.get("/api/auth/me")).status_code == 200


async def test_callback_from_a_different_browser_is_rejected(client, alice, test_engine, fake_providers):
    """Login CSRF: an attacker starts a login as themselves and tricks the victim's browser
    into completing it. The victim's browser never received the nonce cookie, so it fails.
    """
    await _link(test_engine, alice.id)
    _, state = await _begin_login(client)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as victim:
        resp = await _callback(victim, state)
        assert resp.headers["location"] == "/login?oauth=error"
        assert (await victim.get("/api/auth/me")).status_code == 401


async def test_garbage_state_is_rejected(client, alice, test_engine, fake_providers):
    await _link(test_engine, alice.id)
    await _begin_login(client)
    resp = await _callback(client, "garbage")
    assert resp.headers["location"] == "/login?oauth=error"


async def test_provider_failure_during_login_is_reported_not_raised(client, alice, test_engine, fake_providers):
    class Broken(FakeOAuthClient):
        async def get_access_token(self, code, redirect_uri):
            raise RuntimeError("provider down")

    fake_providers["google"] = Broken("google-id-1", "x@example.com")
    await _link(test_engine, alice.id)
    _, state = await _begin_login(client)
    resp = await _callback(client, state)
    assert resp.headers["location"] == "/login?oauth=error"
