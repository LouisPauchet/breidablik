from datetime import date

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


async def test_create_and_list_absence(client, alice):
    await _login(client, "alice@example.com")
    resp = await client.post(
        "/api/absences",
        json={"start_date": "2026-09-01", "end_date": "2026-09-10", "reason": "Holiday"},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["user_id"] == str(alice.id)
    assert body["reason"] == "Holiday"

    listing = await client.get("/api/absences")
    assert listing.status_code == 200
    assert len(listing.json()) == 1


async def test_end_date_before_start_date_rejected(client, alice):
    await _login(client, "alice@example.com")
    resp = await client.post(
        "/api/absences", json={"start_date": "2026-09-10", "end_date": "2026-09-01"}
    )
    assert resp.status_code == 422


async def test_absences_visible_to_other_members(client, alice, test_engine):
    await _create_user(test_engine, "bob@example.com", "Bob")
    await _login(client, "alice@example.com")
    await client.post("/api/absences", json={"start_date": "2026-09-01", "end_date": "2026-09-10"})
    await client.post("/api/auth/logout")

    await _login(client, "bob@example.com")
    listing = await client.get("/api/absences")
    assert len(listing.json()) == 1


async def test_only_owner_can_delete_absence(client, alice, test_engine):
    bob = await _create_user(test_engine, "bob@example.com", "Bob")
    await _login(client, "alice@example.com")
    create_resp = await client.post(
        "/api/absences", json={"start_date": "2026-09-01", "end_date": "2026-09-10"}
    )
    absence_id = create_resp.json()["id"]
    await client.post("/api/auth/logout")

    await _login(client, "bob@example.com")
    forbidden = await client.delete(f"/api/absences/{absence_id}")
    assert forbidden.status_code == 403
    await client.post("/api/auth/logout")

    await _login(client, "alice@example.com")
    ok = await client.delete(f"/api/absences/{absence_id}")
    assert ok.status_code == 204


async def test_owner_can_update_absence(client, alice):
    await _login(client, "alice@example.com")
    create_resp = await client.post(
        "/api/absences",
        json={"start_date": "2026-09-01", "end_date": "2026-09-10", "reason": "Holiday"},
    )
    absence_id = create_resp.json()["id"]

    resp = await client.patch(
        f"/api/absences/{absence_id}",
        json={"end_date": "2026-09-15", "reason": "Extended holiday"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["start_date"] == "2026-09-01"
    assert body["end_date"] == "2026-09-15"
    assert body["reason"] == "Extended holiday"


async def test_update_rejects_end_before_start(client, alice):
    await _login(client, "alice@example.com")
    create_resp = await client.post(
        "/api/absences", json={"start_date": "2026-09-01", "end_date": "2026-09-10"}
    )
    absence_id = create_resp.json()["id"]

    resp = await client.patch(f"/api/absences/{absence_id}", json={"end_date": "2026-08-31"})
    assert resp.status_code == 422


async def test_only_owner_can_update_absence(client, alice, test_engine):
    await _create_user(test_engine, "bob@example.com", "Bob")
    await _login(client, "alice@example.com")
    create_resp = await client.post(
        "/api/absences", json={"start_date": "2026-09-01", "end_date": "2026-09-10"}
    )
    absence_id = create_resp.json()["id"]
    await client.post("/api/auth/logout")

    await _login(client, "bob@example.com")
    forbidden = await client.patch(f"/api/absences/{absence_id}", json={"reason": "hacked"})
    assert forbidden.status_code == 403
