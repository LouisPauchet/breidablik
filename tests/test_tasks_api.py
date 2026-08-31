from datetime import date, timedelta

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


async def test_create_and_list_task(client, alice, test_engine):
    bob = await _create_user(test_engine, "bob@example.com", "Bob")
    await _login(client, "alice@example.com")

    resp = await client.post(
        "/api/tasks",
        json={
            "title": "Buy lightbulbs",
            "due_date": "2026-09-15",
            "assignee_user_ids": [str(alice.id), str(bob.id)],
        },
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["title"] == "Buy lightbulbs"
    assert body["is_done"] is False
    assert set(body["assignee_user_ids"]) == {str(alice.id), str(bob.id)}

    listing = await client.get("/api/tasks")
    assert listing.status_code == 200
    assert len(listing.json()) == 1


async def test_toggle_task_done(client, alice):
    await _login(client, "alice@example.com")
    create_resp = await client.post(
        "/api/tasks", json={"title": "Fix the fence", "assignee_user_ids": [str(alice.id)]}
    )
    task_id = create_resp.json()["id"]

    toggled = await client.post(f"/api/tasks/{task_id}/toggle-done")
    assert toggled.status_code == 200
    assert toggled.json()["is_done"] is True
    assert toggled.json()["done_by_id"] == str(alice.id)
    assert toggled.json()["done_at"] is not None

    toggled_back = await client.post(f"/api/tasks/{task_id}/toggle-done")
    assert toggled_back.json()["is_done"] is False
    assert toggled_back.json()["done_by_id"] is None
    assert toggled_back.json()["done_at"] is None


async def test_update_task_fields_and_reassign(client, alice, test_engine):
    bob = await _create_user(test_engine, "bob@example.com", "Bob")
    await _login(client, "alice@example.com")
    create_resp = await client.post(
        "/api/tasks", json={"title": "Original", "assignee_user_ids": [str(alice.id)]}
    )
    task_id = create_resp.json()["id"]

    updated = await client.patch(
        f"/api/tasks/{task_id}",
        json={"title": "Renamed", "assignee_user_ids": [str(bob.id)]},
    )
    assert updated.status_code == 200
    body = updated.json()
    assert body["title"] == "Renamed"
    assert body["assignee_user_ids"] == [str(bob.id)]


async def test_delete_task(client, alice):
    await _login(client, "alice@example.com")
    create_resp = await client.post(
        "/api/tasks", json={"title": "One-off", "assignee_user_ids": [str(alice.id)]}
    )
    task_id = create_resp.json()["id"]

    deleted = await client.delete(f"/api/tasks/{task_id}")
    assert deleted.status_code == 204

    listing = await client.get("/api/tasks")
    assert listing.json() == []


async def test_list_orders_incomplete_first_then_by_due_date(client, alice):
    await _login(client, "alice@example.com")
    today = date.today()

    later = await client.post(
        "/api/tasks",
        json={
            "title": "Later",
            "due_date": (today + timedelta(days=10)).isoformat(),
            "assignee_user_ids": [str(alice.id)],
        },
    )
    no_date = await client.post(
        "/api/tasks", json={"title": "No due date", "assignee_user_ids": [str(alice.id)]}
    )
    sooner = await client.post(
        "/api/tasks",
        json={
            "title": "Sooner",
            "due_date": (today + timedelta(days=1)).isoformat(),
            "assignee_user_ids": [str(alice.id)],
        },
    )
    # Mark "Sooner" done — it should drop to the end despite its earlier due date.
    await client.post(f"/api/tasks/{sooner.json()['id']}/toggle-done")

    listing = await client.get("/api/tasks")
    titles = [t["title"] for t in listing.json()]
    assert titles == ["Later", "No due date", "Sooner"]
