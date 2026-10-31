import json

from fastapi_users.jwt import decode_jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.config import get_settings
from app.models.audit import AuditLog
from app.models.notification import Notification
from tests.test_admin_api import _create_user, _login


def _decode(token: str) -> dict:
    return decode_jwt(token, get_settings().secret_key, ["fastapi-users:reset"])


async def test_admin_can_generate_a_reset_link_token(client, alice, test_engine):
    bob = await _create_user(test_engine, "bob@example.com", "Bob")
    await _login(client, "alice@example.com")

    resp = await client.post(f"/api/admin/users/{bob.id}/password-reset", json={})
    assert resp.status_code == 200
    body = resp.json()
    assert body["expires_in"] == 24 * 3600

    claims = _decode(body["token"])
    assert claims["sub"] == str(bob.id)
    assert claims["reset_2fa"] is False


async def test_reset_2fa_choice_is_carried_in_the_token(client, alice, test_engine):
    bob = await _create_user(test_engine, "bob@example.com", "Bob")
    await _login(client, "alice@example.com")

    resp = await client.post(f"/api/admin/users/{bob.id}/password-reset", json={"reset_2fa": True})
    assert _decode(resp.json()["token"])["reset_2fa"] is True


async def test_generating_a_link_changes_nothing_until_redeemed(client, alice, test_engine):
    bob = await _create_user(test_engine, "bob@example.com", "Bob")
    await _login(client, "alice@example.com")
    await client.post(f"/api/admin/users/{bob.id}/password-reset", json={"reset_2fa": True})
    await client.post("/api/auth/logout")

    # Bob's old password still works: the link is only a capability, not a reset.
    resp = await client.post(
        "/api/auth/login", json={"email": "bob@example.com", "password": "correcthorsebatterystaple"}
    )
    assert resp.status_code == 200


async def test_non_admin_cannot_generate_a_reset_link(client, alice, test_engine):
    bob = await _create_user(test_engine, "bob@example.com", "Bob")
    await _create_user(test_engine, "carol@example.com", "Carol")
    await _login(client, "carol@example.com")

    resp = await client.post(f"/api/admin/users/{bob.id}/password-reset", json={})
    assert resp.status_code == 403


async def test_unknown_user_404s(client, alice):
    await _login(client, "alice@example.com")
    resp = await client.post(
        "/api/admin/users/00000000-0000-0000-0000-000000000000/password-reset", json={}
    )
    assert resp.status_code == 404
    assert resp.json()["detail"] == "USER_NOT_FOUND"


async def test_pending_invite_cannot_get_a_reset_link(client, alice):
    await _login(client, "alice@example.com")
    created = await client.post(
        "/api/admin/users", json={"email": "carol@example.com", "display_name": "Carol"}
    )
    resp = await client.post(f"/api/admin/users/{created.json()['id']}/password-reset", json={})
    assert resp.status_code == 400
    assert resp.json()["detail"] == "USER_NOT_ACTIVE"


async def test_generating_a_link_writes_audit_entry_and_notifies_the_member(client, alice, test_engine):
    bob = await _create_user(test_engine, "bob@example.com", "Bob")
    await _login(client, "alice@example.com")
    await client.post(f"/api/admin/users/{bob.id}/password-reset", json={"reset_2fa": True})

    maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with maker() as session:
        entry = (await session.execute(select(AuditLog))).scalar_one()
        notification = (await session.execute(select(Notification))).scalar_one()

    assert entry.actor_id == alice.id
    assert entry.target_user_id == bob.id
    assert entry.action == "user.password_reset_issued"
    assert json.loads(entry.detail) == {"reset_2fa": True}
    # The token itself must never be written to the log.
    assert "token" not in entry.detail

    assert notification.user_id == bob.id
    assert notification.kind == "password_reset_issued"
