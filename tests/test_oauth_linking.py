from urllib.parse import parse_qs, urlparse

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.auth.oauth import get_oauth_clients
from app.config import get_settings
from app.main import app
from app.models.oauth import OAuthAccount
from app.models.user import User
from tests.test_admin_api import _create_user, _login


class FakeOAuthClient:
    """Stands in for an httpx-oauth client: no network, fixed identity at the provider."""

    def __init__(self, account_id: str, email: str | None):
        self.account_id = account_id
        self.email = email

    async def get_authorization_url(self, redirect_uri, state=None, scope=None):
        return f"https://provider.example/authorize?state={state}&redirect_uri={redirect_uri}"

    async def get_access_token(self, code, redirect_uri):
        return {"access_token": f"token-for-{code}"}

    async def get_id_email(self, token):
        return self.account_id, self.email


@pytest.fixture
def fake_providers():
    clients = {
        "google": FakeOAuthClient("google-id-1", "bob@gmail.example"),
        "github": FakeOAuthClient("github-id-1", "bob@github.example"),
    }
    app.dependency_overrides[get_oauth_clients] = lambda: clients
    return clients


async def _start_link(client, provider="google") -> str:
    resp = await client.post(f"/api/auth/oauth/{provider}/link")
    assert resp.status_code == 200
    return parse_qs(urlparse(resp.json()["authorization_url"]).query)["state"][0]


async def _accounts(test_engine) -> list[OAuthAccount]:
    maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with maker() as session:
        return list((await session.execute(select(OAuthAccount))).scalars())


def test_provider_is_enabled_only_when_both_id_and_secret_are_set(monkeypatch):
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "id")
    monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "")
    monkeypatch.setenv("GITHUB_CLIENT_ID", "id")
    monkeypatch.setenv("GITHUB_CLIENT_SECRET", "secret")
    get_settings.cache_clear()
    try:
        assert set(get_oauth_clients()) == {"github"}
    finally:
        get_settings.cache_clear()


async def test_providers_endpoint_is_empty_when_unconfigured(client, monkeypatch):
    for name in ("GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET", "GITHUB_CLIENT_ID", "GITHUB_CLIENT_SECRET"):
        monkeypatch.setenv(name, "")
    get_settings.cache_clear()
    try:
        resp = await client.get("/api/auth/oauth/providers")
    finally:
        get_settings.cache_clear()
    assert resp.status_code == 200
    assert resp.json() == []


async def test_providers_endpoint_lists_configured_providers(client, fake_providers):
    resp = await client.get("/api/auth/oauth/providers")
    assert sorted(resp.json()) == ["github", "google"]


async def test_linking_requires_login(client, fake_providers):
    assert (await client.post("/api/auth/oauth/google/link")).status_code == 401


async def test_unconfigured_provider_cannot_be_linked(client, alice, fake_providers):
    await _login(client, "alice@example.com")
    assert (await client.post("/api/auth/oauth/microsoft/link")).status_code == 404


async def test_link_then_callback_links_the_account(client, alice, test_engine, fake_providers):
    await _login(client, "alice@example.com")
    state = await _start_link(client)

    resp = await client.get(f"/api/auth/oauth/google/callback?code=abc&state={state}")
    assert resp.status_code == 302
    assert resp.headers["location"] == "/profile?oauth=linked"

    [account] = await _accounts(test_engine)
    assert (account.user_id, account.provider, account.account_id) == (alice.id, "google", "google-id-1")
    assert account.account_email == "bob@gmail.example"

    listing = await client.get("/api/auth/oauth/accounts")
    assert listing.json() == [{"provider": "google", "account_email": "bob@gmail.example"}]


async def test_linking_never_creates_a_user(client, alice, test_engine, fake_providers):
    await _login(client, "alice@example.com")
    state = await _start_link(client)
    await client.get(f"/api/auth/oauth/google/callback?code=abc&state={state}")

    maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with maker() as session:
        emails = {u.email for u in (await session.execute(select(User))).scalars()}
    assert emails == {"alice@example.com"}


async def test_callback_with_a_garbage_or_missing_state_links_nothing(client, alice, test_engine, fake_providers):
    await _login(client, "alice@example.com")
    for query in ("code=abc&state=garbage", "code=abc"):
        resp = await client.get(f"/api/auth/oauth/google/callback?{query}")
        assert resp.status_code == 302
        assert resp.headers["location"] == "/profile?oauth=error"
    assert await _accounts(test_engine) == []


async def test_state_started_by_one_member_cannot_be_completed_by_another(client, alice, test_engine, fake_providers):
    await _create_user(test_engine, "carol@example.com", "Carol")
    await _login(client, "alice@example.com")
    state = await _start_link(client)
    await client.post("/api/auth/logout")

    # An attacker who tricks Carol into opening a callback URL with Alice's state must not
    # get Alice's provider identity attached to Carol.
    await _login(client, "carol@example.com")
    resp = await client.get(f"/api/auth/oauth/google/callback?code=abc&state={state}")
    assert resp.headers["location"] == "/profile?oauth=error"
    assert await _accounts(test_engine) == []


async def test_callback_without_a_session_links_nothing(client, alice, test_engine, fake_providers):
    await _login(client, "alice@example.com")
    state = await _start_link(client)
    await client.post("/api/auth/logout")

    resp = await client.get(f"/api/auth/oauth/google/callback?code=abc&state={state}")
    assert resp.status_code == 302
    assert "oauth=error" in resp.headers["location"]
    assert await _accounts(test_engine) == []


async def test_provider_identity_already_linked_to_someone_else_is_refused(client, alice, test_engine, fake_providers):
    carol = await _create_user(test_engine, "carol@example.com", "Carol")
    maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with maker() as session:
        session.add(OAuthAccount(user_id=carol.id, provider="google", account_id="google-id-1"))
        await session.commit()

    await _login(client, "alice@example.com")
    state = await _start_link(client)
    resp = await client.get(f"/api/auth/oauth/google/callback?code=abc&state={state}")

    assert resp.headers["location"] == "/profile?oauth=error"
    [account] = await _accounts(test_engine)
    assert account.user_id == carol.id


async def test_a_provider_can_only_be_linked_once_per_member(client, alice, fake_providers):
    await _login(client, "alice@example.com")
    state = await _start_link(client)
    await client.get(f"/api/auth/oauth/google/callback?code=abc&state={state}")

    again = await client.post("/api/auth/oauth/google/link")
    assert again.status_code == 400
    assert again.json()["detail"] == "ALREADY_LINKED"


async def test_unlink_removes_the_account(client, alice, test_engine, fake_providers):
    await _login(client, "alice@example.com")
    state = await _start_link(client)
    await client.get(f"/api/auth/oauth/google/callback?code=abc&state={state}")

    resp = await client.delete("/api/auth/oauth/google")
    assert resp.status_code == 200
    assert await _accounts(test_engine) == []
    assert (await client.delete("/api/auth/oauth/google")).status_code == 404


async def test_cannot_unlink_the_last_way_to_sign_in(client, alice, test_engine, fake_providers):
    await _login(client, "alice@example.com")
    state = await _start_link(client)
    await client.get(f"/api/auth/oauth/google/callback?code=abc&state={state}")

    maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with maker() as session:
        user = (await session.execute(select(User).where(User.id == alice.id))).scalar_one()
        user.password_login_enabled = False
        await session.commit()

    resp = await client.delete("/api/auth/oauth/google")
    assert resp.status_code == 400
    assert resp.json()["detail"] == "LAST_SIGNIN_METHOD"
    assert len(await _accounts(test_engine)) == 1


async def test_can_unlink_one_of_two_linked_accounts_without_a_password(client, alice, test_engine, fake_providers):
    await _login(client, "alice@example.com")
    for provider, code in (("google", "a"), ("github", "b")):
        state = await _start_link(client, provider)
        await client.get(f"/api/auth/oauth/{provider}/callback?code={code}&state={state}")

    maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with maker() as session:
        user = (await session.execute(select(User).where(User.id == alice.id))).scalar_one()
        user.password_login_enabled = False
        await session.commit()

    assert (await client.delete("/api/auth/oauth/google")).status_code == 200
    assert (await client.delete("/api/auth/oauth/github")).status_code == 400
