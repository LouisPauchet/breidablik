from fastapi_users.db import SQLAlchemyUserDatabase
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.auth.users import UserManager
from app.models.notification import PushSubscription
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


async def test_subscribe_creates_push_subscription(client, alice, test_engine):
    await _login(client, "alice@example.com")
    resp = await client.post(
        "/api/notifications/push-subscriptions",
        json={"endpoint": "https://push.example.com/ep1", "keys": {"p256dh": "p", "auth": "a"}},
    )
    assert resp.status_code == 201

    maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with maker() as session:
        result = await session.execute(
            select(PushSubscription).where(PushSubscription.endpoint == "https://push.example.com/ep1")
        )
        sub = result.scalar_one()
        assert sub.user_id == alice.id


async def test_unsubscribe_only_deletes_own_subscription(client, alice, test_engine):
    # Regression test: DELETE /push-subscriptions used to look up and delete by `endpoint`
    # alone, with no check that it belonged to the calling user — unlike every other route in
    # this file. Bob deleting Alice's subscription must be a no-op, not succeed.
    bob = await _create_user(test_engine, "bob@example.com", "Bob")

    maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with maker() as session:
        session.add(
            PushSubscription(
                user_id=alice.id, endpoint="https://push.example.com/alice-ep", p256dh="p", auth="a"
            )
        )
        await session.commit()

    await _login(client, "bob@example.com")
    resp = await client.delete(
        "/api/notifications/push-subscriptions", params={"endpoint": "https://push.example.com/alice-ep"}
    )
    assert resp.status_code == 200

    async with maker() as session:
        result = await session.execute(
            select(PushSubscription).where(PushSubscription.endpoint == "https://push.example.com/alice-ep")
        )
        assert result.scalar_one_or_none() is not None


async def test_unsubscribe_deletes_own_subscription(client, alice):
    await _login(client, "alice@example.com")
    await client.post(
        "/api/notifications/push-subscriptions",
        json={"endpoint": "https://push.example.com/ep2", "keys": {"p256dh": "p", "auth": "a"}},
    )

    resp = await client.delete(
        "/api/notifications/push-subscriptions", params={"endpoint": "https://push.example.com/ep2"}
    )
    assert resp.status_code == 200
