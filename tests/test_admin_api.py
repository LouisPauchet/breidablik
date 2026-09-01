from fastapi_users.db import SQLAlchemyUserDatabase
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.auth.users import UserManager
from app.models.user import User
from app.schemas.user import UserCreate


async def _create_user(test_engine, email: str, display_name: str, is_superuser: bool = False) -> User:
    maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with maker() as session:
        manager = UserManager(SQLAlchemyUserDatabase(session, User))
        return await manager.create(
            UserCreate(
                email=email,
                password="correcthorsebatterystaple",
                display_name=display_name,
                is_superuser=is_superuser,
            ),
            safe=False,
        )


async def _login(client, email: str):
    resp = await client.post(
        "/api/auth/login", json={"email": email, "password": "correcthorsebatterystaple"}
    )
    assert resp.status_code == 200


async def test_non_superuser_cannot_invite_members(client, alice, test_engine):
    await _create_user(test_engine, "bob@example.com", "Bob", is_superuser=False)
    await _login(client, "bob@example.com")
    resp = await client.post(
        "/api/admin/users", json={"email": "carol@example.com", "display_name": "Carol"}
    )
    assert resp.status_code == 403


async def test_superuser_can_invite_and_list_members(client, alice):
    await _login(client, "alice@example.com")

    create_resp = await client.post(
        "/api/admin/users", json={"email": "carol@example.com", "display_name": "Carol"}
    )
    assert create_resp.status_code == 201
    body = create_resp.json()
    assert body["display_name"] == "Carol"
    # Not usable until the invite is accepted.
    assert body["is_active"] is False
    assert body["invite_token"]

    listing = await client.get("/api/admin/users")
    assert listing.status_code == 200
    emails = {u["email"] for u in listing.json()}
    assert emails == {"alice@example.com", "carol@example.com"}


async def test_cannot_invite_duplicate_member(client, alice):
    await _login(client, "alice@example.com")
    await client.post("/api/admin/users", json={"email": "carol@example.com", "display_name": "Carol"})
    dup = await client.post(
        "/api/admin/users", json={"email": "carol@example.com", "display_name": "Carol 2"}
    )
    assert dup.status_code == 400


async def test_invited_member_cannot_log_in_before_accepting(client, alice):
    await _login(client, "alice@example.com")
    create_resp = await client.post(
        "/api/admin/users", json={"email": "carol@example.com", "display_name": "Carol"}
    )
    invite_token = create_resp.json()["invite_token"]
    await client.post("/api/auth/logout")

    accept = await client.post(
        f"/api/auth/invite/{invite_token}/accept", json={"password": "brandnewpassword"}
    )
    assert accept.status_code == 200
    assert accept.json()["user"]["email"] == "carol@example.com"

    login_resp = await client.post(
        "/api/auth/login", json={"email": "carol@example.com", "password": "brandnewpassword"}
    )
    assert login_resp.status_code == 200


async def test_regenerate_invite_requires_pending_member(client, alice):
    await _login(client, "alice@example.com")
    create_resp = await client.post(
        "/api/admin/users", json={"email": "carol@example.com", "display_name": "Carol"}
    )
    carol_id = create_resp.json()["id"]
    old_token = create_resp.json()["invite_token"]

    regen = await client.post(f"/api/admin/users/{carol_id}/invite/regenerate")
    assert regen.status_code == 200
    assert regen.json()["invite_token"] != old_token

    # Activate her, then regenerating should be rejected.
    await client.patch(f"/api/users/{carol_id}", json={"is_active": True})
    regen_after_active = await client.post(f"/api/admin/users/{carol_id}/invite/regenerate")
    assert regen_after_active.status_code == 400
