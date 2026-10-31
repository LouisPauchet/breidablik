from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.main import app
from app.models.audit import AuditLog
from app.models.notification import Notification
from app.models.user import DeviceTrust, User
from tests.test_admin_api import _create_user, _login


async def _reload(test_engine, user_id) -> User:
    maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with maker() as session:
        return (await session.execute(select(User).where(User.id == user_id))).scalar_one()


async def _rows(test_engine, model):
    maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with maker() as session:
        return list((await session.execute(select(model))).scalars())


# --- force logout -----------------------------------------------------------------------


async def test_revoke_sessions_logs_the_member_out_everywhere(client, alice, test_engine):
    bob = await _create_user(test_engine, "bob@example.com", "Bob")
    maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with maker() as session:
        session.add(DeviceTrust(user_id=bob.id, device_id="dev-1", pin_hash="x"))
        await session.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as bobs_device:
        await _login(bobs_device, "bob@example.com")
        assert (await bobs_device.get("/api/auth/me")).status_code == 200

        await _login(client, "alice@example.com")
        resp = await client.post(f"/api/admin/users/{bob.id}/revoke-sessions")
        assert resp.status_code == 200

        assert (await bobs_device.get("/api/auth/me")).status_code == 401

    [device] = await _rows(test_engine, DeviceTrust)
    assert device.revoked_at is not None
    # Not a lockout: the member can simply sign in again.
    again = await client.post(
        "/api/auth/login", json={"email": "bob@example.com", "password": "correcthorsebatterystaple"}
    )
    assert again.status_code == 200


async def test_revoke_sessions_is_audit_logged_and_notifies(client, alice, test_engine):
    bob = await _create_user(test_engine, "bob@example.com", "Bob")
    await _login(client, "alice@example.com")
    await client.post(f"/api/admin/users/{bob.id}/revoke-sessions")

    [entry] = await _rows(test_engine, AuditLog)
    assert (entry.actor_id, entry.target_user_id, entry.action) == (alice.id, bob.id, "user.sessions_revoked")
    [note] = await _rows(test_engine, Notification)
    assert (note.user_id, note.kind) == (bob.id, "sessions_revoked")


async def test_revoke_sessions_guards(client, alice, test_engine):
    bob = await _create_user(test_engine, "bob@example.com", "Bob")
    await _create_user(test_engine, "carol@example.com", "Carol")
    zero = "00000000-0000-0000-0000-000000000000"

    await _login(client, "carol@example.com")
    assert (await client.post(f"/api/admin/users/{bob.id}/revoke-sessions")).status_code == 403
    await client.post("/api/auth/logout")

    await _login(client, "alice@example.com")
    assert (await client.post(f"/api/admin/users/{zero}/revoke-sessions")).status_code == 404
    own = await client.post(f"/api/admin/users/{alice.id}/revoke-sessions")
    assert own.status_code == 400
    assert own.json()["detail"] == "CANNOT_ACT_ON_SELF"


# --- role change ------------------------------------------------------------------------


async def test_admin_can_promote_and_demote(client, alice, test_engine):
    bob = await _create_user(test_engine, "bob@example.com", "Bob")
    await _login(client, "alice@example.com")

    promoted = await client.patch(f"/api/admin/users/{bob.id}/role", json={"is_superuser": True})
    assert promoted.status_code == 200
    assert promoted.json()["is_superuser"] is True
    assert (await _reload(test_engine, bob.id)).is_superuser is True

    demoted = await client.patch(f"/api/admin/users/{bob.id}/role", json={"is_superuser": False})
    assert demoted.json()["is_superuser"] is False
    assert (await _reload(test_engine, bob.id)).is_superuser is False


async def test_role_change_is_audit_logged_and_notifies(client, alice, test_engine):
    bob = await _create_user(test_engine, "bob@example.com", "Bob")
    await _login(client, "alice@example.com")
    await client.patch(f"/api/admin/users/{bob.id}/role", json={"is_superuser": True})

    [entry] = await _rows(test_engine, AuditLog)
    assert (entry.target_user_id, entry.action) == (bob.id, "user.role_changed")
    assert entry.detail == '{"is_superuser": true}'
    [note] = await _rows(test_engine, Notification)
    assert (note.user_id, note.kind) == (bob.id, "role_changed")


async def test_setting_the_role_a_member_already_has_is_a_silent_no_op(client, alice, test_engine):
    bob = await _create_user(test_engine, "bob@example.com", "Bob")
    await _login(client, "alice@example.com")
    resp = await client.patch(f"/api/admin/users/{bob.id}/role", json={"is_superuser": False})
    assert resp.status_code == 200
    assert await _rows(test_engine, AuditLog) == []
    assert await _rows(test_engine, Notification) == []


async def test_cannot_change_your_own_role(client, alice):
    await _login(client, "alice@example.com")
    resp = await client.patch(f"/api/admin/users/{alice.id}/role", json={"is_superuser": False})
    assert resp.status_code == 400
    assert resp.json()["detail"] == "CANNOT_ACT_ON_SELF"


async def test_non_admin_cannot_change_roles(client, alice, test_engine):
    bob = await _create_user(test_engine, "bob@example.com", "Bob")
    await _create_user(test_engine, "carol@example.com", "Carol")
    await _login(client, "carol@example.com")
    resp = await client.patch(f"/api/admin/users/{bob.id}/role", json={"is_superuser": True})
    assert resp.status_code == 403
    assert (await _reload(test_engine, bob.id)).is_superuser is False


async def test_an_admin_can_demote_another_admin_while_one_remains(client, alice, test_engine):
    # The last-admin guard is covered in test_admin_guards; through the API the acting admin
    # is always a second active admin, so it can only trip on a race.
    dave = await _create_user(test_engine, "dave@example.com", "Dave", is_superuser=True)
    await _login(client, "alice@example.com")
    resp = await client.patch(f"/api/admin/users/{dave.id}/role", json={"is_superuser": False})
    assert resp.status_code == 200


# --- the stock user PATCH can no longer sidestep the guards -----------------------------


async def test_user_patch_cannot_change_active_or_admin_flags(client, alice, test_engine):
    bob = await _create_user(test_engine, "bob@example.com", "Bob")
    await _login(client, "alice@example.com")

    assert (await client.patch(f"/api/users/{bob.id}", json={"is_active": False})).status_code == 422
    assert (await client.patch(f"/api/users/{bob.id}", json={"is_superuser": True})).status_code == 422
    assert (await client.patch(f"/api/users/{alice.id}", json={"is_superuser": False})).status_code == 422

    user = await _reload(test_engine, bob.id)
    assert (user.is_active, user.is_superuser) == (True, False)


async def test_user_patch_still_edits_ordinary_profile_fields(client, alice):
    await _login(client, "alice@example.com")
    resp = await client.patch("/api/users/me", json={"display_name": "Alice B"})
    assert resp.status_code == 200
    assert resp.json()["display_name"] == "Alice B"
