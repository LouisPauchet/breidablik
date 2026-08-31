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


async def test_non_superuser_cannot_create_members(client, alice, test_engine):
    await _create_user(test_engine, "bob@example.com", "Bob", is_superuser=False)
    await _login(client, "bob@example.com")
    resp = await client.post(
        "/api/admin/users",
        json={"email": "carol@example.com", "password": "correcthorsebatterystaple", "display_name": "Carol"},
    )
    assert resp.status_code == 403


async def test_superuser_can_create_and_list_members(client, alice):
    await _login(client, "alice@example.com")

    create_resp = await client.post(
        "/api/admin/users",
        json={"email": "carol@example.com", "password": "correcthorsebatterystaple", "display_name": "Carol"},
    )
    assert create_resp.status_code == 201
    assert create_resp.json()["display_name"] == "Carol"

    listing = await client.get("/api/admin/users")
    assert listing.status_code == 200
    emails = {u["email"] for u in listing.json()}
    assert emails == {"alice@example.com", "carol@example.com"}


async def test_cannot_create_duplicate_member(client, alice):
    await _login(client, "alice@example.com")
    await client.post(
        "/api/admin/users",
        json={"email": "carol@example.com", "password": "correcthorsebatterystaple", "display_name": "Carol"},
    )
    dup = await client.post(
        "/api/admin/users",
        json={"email": "carol@example.com", "password": "correcthorsebatterystaple", "display_name": "Carol 2"},
    )
    assert dup.status_code == 400
