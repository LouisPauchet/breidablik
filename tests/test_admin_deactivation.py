from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.main import app
from app.models.audit import AuditLog
from app.models.notification import Notification
from app.models.task import Task
from app.models.user import DeviceTrust, User
from tests.test_admin_api import _create_user, _login


async def _reload(test_engine, user_id) -> User:
    maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with maker() as session:
        return (await session.execute(select(User).where(User.id == user_id))).scalar_one()


async def _audit_actions(test_engine) -> list[str]:
    maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with maker() as session:
        return [e.action for e in (await session.execute(select(AuditLog).order_by(AuditLog.created_at))).scalars()]


async def test_non_admin_cannot_deactivate(client, alice, test_engine):
    bob = await _create_user(test_engine, "bob@example.com", "Bob")
    await _create_user(test_engine, "carol@example.com", "Carol")
    await _login(client, "carol@example.com")
    resp = await client.post(f"/api/admin/users/{bob.id}/deactivate")
    assert resp.status_code == 403


async def test_deactivate_marks_user_inactive_with_timestamp(client, alice, test_engine):
    bob = await _create_user(test_engine, "bob@example.com", "Bob")
    await _login(client, "alice@example.com")

    resp = await client.post(f"/api/admin/users/{bob.id}/deactivate")
    assert resp.status_code == 200
    assert resp.json()["is_active"] is False
    assert resp.json()["deactivated_at"] is not None

    user = await _reload(test_engine, bob.id)
    assert user.is_active is False
    assert user.deactivated_at is not None


async def test_deactivated_member_cannot_log_in(client, alice, test_engine):
    bob = await _create_user(test_engine, "bob@example.com", "Bob")
    await _login(client, "alice@example.com")
    await client.post(f"/api/admin/users/{bob.id}/deactivate")
    await client.post("/api/auth/logout")

    resp = await client.post(
        "/api/auth/login", json={"email": "bob@example.com", "password": "correcthorsebatterystaple"}
    )
    assert resp.status_code == 400


async def test_deactivation_kills_existing_sessions_and_pin_shortcuts(client, alice, test_engine):
    bob = await _create_user(test_engine, "bob@example.com", "Bob")
    maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with maker() as session:
        session.add(DeviceTrust(user_id=bob.id, device_id="dev-1", pin_hash="x"))
        await session.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as bobs_device:
        await _login(bobs_device, "bob@example.com")
        assert (await bobs_device.get("/api/auth/me")).status_code == 200

        await _login(client, "alice@example.com")
        await client.post(f"/api/admin/users/{bob.id}/deactivate")

        assert (await bobs_device.get("/api/auth/me")).status_code == 401

    async with maker() as session:
        device = (await session.execute(select(DeviceTrust))).scalar_one()
    assert device.revoked_at is not None


async def test_deactivation_keeps_the_members_data(client, alice, test_engine):
    bob = await _create_user(test_engine, "bob@example.com", "Bob")
    maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with maker() as session:
        session.add(Task(title="Fix the bike", created_by_id=bob.id))
        await session.commit()

    await _login(client, "alice@example.com")
    await client.post(f"/api/admin/users/{bob.id}/deactivate")

    async with maker() as session:
        task = (await session.execute(select(Task))).scalar_one()
    assert task.created_by_id == bob.id
    assert (await _reload(test_engine, bob.id)).email == "bob@example.com"


async def test_cannot_deactivate_yourself(client, alice):
    await _login(client, "alice@example.com")
    resp = await client.post(f"/api/admin/users/{alice.id}/deactivate")
    assert resp.status_code == 400
    assert resp.json()["detail"] == "CANNOT_ACT_ON_SELF"


async def test_an_admin_can_deactivate_another_admin_while_one_remains(client, alice, test_engine):
    # The last-admin guard itself is covered in test_admin_guards; through the API the acting
    # admin is always a second active admin, so it can only trip on a race.
    dave = await _create_user(test_engine, "dave@example.com", "Dave", is_superuser=True)
    await _login(client, "dave@example.com")

    resp = await client.post(f"/api/admin/users/{alice.id}/deactivate")
    assert resp.status_code == 200
    assert (await _reload(test_engine, dave.id)).is_active is True


async def test_cannot_deactivate_a_pending_invite_or_an_already_deactivated_member(client, alice, test_engine):
    bob = await _create_user(test_engine, "bob@example.com", "Bob")
    await _login(client, "alice@example.com")
    pending = await client.post(
        "/api/admin/users", json={"email": "carol@example.com", "display_name": "Carol"}
    )
    resp = await client.post(f"/api/admin/users/{pending.json()['id']}/deactivate")
    assert resp.status_code == 400
    assert resp.json()["detail"] == "USER_NOT_ACTIVE"

    await client.post(f"/api/admin/users/{bob.id}/deactivate")
    again = await client.post(f"/api/admin/users/{bob.id}/deactivate")
    assert again.status_code == 400
    assert again.json()["detail"] == "USER_NOT_ACTIVE"


async def test_unknown_user_404s(client, alice):
    await _login(client, "alice@example.com")
    zero = "00000000-0000-0000-0000-000000000000"
    assert (await client.post(f"/api/admin/users/{zero}/deactivate")).status_code == 404
    assert (await client.post(f"/api/admin/users/{zero}/reactivate")).status_code == 404


async def test_reactivate_restores_login(client, alice, test_engine):
    bob = await _create_user(test_engine, "bob@example.com", "Bob")
    await _login(client, "alice@example.com")
    await client.post(f"/api/admin/users/{bob.id}/deactivate")

    resp = await client.post(f"/api/admin/users/{bob.id}/reactivate")
    assert resp.status_code == 200
    assert resp.json()["is_active"] is True
    assert resp.json()["deactivated_at"] is None
    await client.post("/api/auth/logout")

    login = await client.post(
        "/api/auth/login", json={"email": "bob@example.com", "password": "correcthorsebatterystaple"}
    )
    assert login.status_code == 200


async def test_reactivate_is_refused_for_pending_invites_and_active_members(client, alice, test_engine):
    bob = await _create_user(test_engine, "bob@example.com", "Bob")
    await _login(client, "alice@example.com")
    pending = await client.post(
        "/api/admin/users", json={"email": "carol@example.com", "display_name": "Carol"}
    )

    resp = await client.post(f"/api/admin/users/{pending.json()['id']}/reactivate")
    assert resp.status_code == 400
    assert resp.json()["detail"] == "USER_PENDING_INVITE"

    resp = await client.post(f"/api/admin/users/{bob.id}/reactivate")
    assert resp.status_code == 400
    assert resp.json()["detail"] == "USER_ALREADY_ACTIVE"


async def test_invite_regenerate_is_refused_for_a_deactivated_member(client, alice, test_engine):
    bob = await _create_user(test_engine, "bob@example.com", "Bob")
    await _login(client, "alice@example.com")
    await client.post(f"/api/admin/users/{bob.id}/deactivate")

    resp = await client.post(f"/api/admin/users/{bob.id}/invite/regenerate")
    assert resp.status_code == 400
    assert resp.json()["detail"] == "USER_DEACTIVATED"


async def test_deactivated_member_cannot_get_a_reset_link(client, alice, test_engine):
    bob = await _create_user(test_engine, "bob@example.com", "Bob")
    await _login(client, "alice@example.com")
    await client.post(f"/api/admin/users/{bob.id}/deactivate")

    resp = await client.post(f"/api/admin/users/{bob.id}/password-reset", json={})
    assert resp.status_code == 400
    assert resp.json()["detail"] == "USER_NOT_ACTIVE"


async def test_actions_are_audit_logged_and_reactivation_notifies(client, alice, test_engine):
    bob = await _create_user(test_engine, "bob@example.com", "Bob")
    await _login(client, "alice@example.com")
    await client.post(f"/api/admin/users/{bob.id}/deactivate")
    await client.post(f"/api/admin/users/{bob.id}/reactivate")

    assert await _audit_actions(test_engine) == ["user.deactivated", "user.reactivated"]

    maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with maker() as session:
        notifications = (await session.execute(select(Notification))).scalars().all()
    # Deactivation is silent (the member can't sign in to see it); reactivation tells them.
    assert [(n.user_id, n.kind) for n in notifications] == [(bob.id, "account_reactivated")]


async def test_refused_action_leaves_no_audit_entry(client, alice, test_engine):
    await _login(client, "alice@example.com")
    await client.post(f"/api/admin/users/{alice.id}/deactivate")  # refused: self
    assert await _audit_actions(test_engine) == []
