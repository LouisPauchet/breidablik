from fastapi_users.db import SQLAlchemyUserDatabase
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.auth.users import UserManager
from app.models.user import User
from app.schemas.user import UserCreate


async def _create_user(test_engine, email: str, display_name: str) -> User:
    maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with maker() as session:
        manager = UserManager(SQLAlchemyUserDatabase(session, User))
        return await manager.create(
            UserCreate(email=email, password="correcthorsebatterystaple", display_name=display_name),
            safe=False,
        )


async def _login(client, email: str):
    resp = await client.post(
        "/api/auth/login", json={"email": email, "password": "correcthorsebatterystaple"}
    )
    assert resp.status_code == 200


async def test_shared_list_visible_to_everyone(client, alice, test_engine):
    await _create_user(test_engine, "bob@example.com", "Bob")
    await _login(client, "alice@example.com")
    create_resp = await client.post("/api/shopping/lists", json={"name": "Household", "is_private": False})
    assert create_resp.status_code == 201
    assert create_resp.json()["owner_user_id"] is None

    await client.post("/api/auth/logout")
    await _login(client, "bob@example.com")
    listing = await client.get("/api/shopping/lists")
    assert len(listing.json()) == 1
    assert listing.json()[0]["name"] == "Household"


async def test_private_list_invisible_to_other_members(client, alice, test_engine):
    bob = await _create_user(test_engine, "bob@example.com", "Bob")
    await _login(client, "alice@example.com")
    create_resp = await client.post("/api/shopping/lists", json={"name": "Alice's own", "is_private": True})
    assert create_resp.status_code == 201
    assert create_resp.json()["owner_user_id"] == str(alice.id)
    list_id = create_resp.json()["id"]

    await client.post("/api/auth/logout")
    await _login(client, "bob@example.com")
    listing = await client.get("/api/shopping/lists")
    assert listing.json() == []

    forbidden = await client.get(f"/api/shopping/lists/{list_id}")
    assert forbidden.status_code == 403


async def test_private_list_rejects_duty_id(client, alice):
    await _login(client, "alice@example.com")
    resp = await client.post(
        "/api/shopping/lists",
        json={"name": "Mine", "is_private": True, "duty_id": "00000000-0000-0000-0000-000000000000"},
    )
    assert resp.status_code == 422


async def test_add_item_and_toggle_checked(client, alice):
    await _login(client, "alice@example.com")
    create_resp = await client.post("/api/shopping/lists", json={"name": "Household", "is_private": False})
    list_id = create_resp.json()["id"]

    item_resp = await client.post(
        f"/api/shopping/lists/{list_id}/items", json={"name": "Milk", "quantity": "2L"}
    )
    assert item_resp.status_code == 201
    item_id = item_resp.json()["id"]
    assert item_resp.json()["is_checked"] is False

    toggled = await client.patch(f"/api/shopping/items/{item_id}/toggle-checked")
    assert toggled.json()["is_checked"] is True
    assert toggled.json()["checked_by_id"] == str(alice.id)


async def test_cannot_add_item_to_others_private_list(client, alice, test_engine):
    bob = await _create_user(test_engine, "bob@example.com", "Bob")
    await _login(client, "alice@example.com")
    create_resp = await client.post("/api/shopping/lists", json={"name": "Alice's own", "is_private": True})
    list_id = create_resp.json()["id"]

    await client.post("/api/auth/logout")
    await _login(client, "bob@example.com")
    resp = await client.post(f"/api/shopping/lists/{list_id}/items", json={"name": "Sneaky"})
    assert resp.status_code == 403
