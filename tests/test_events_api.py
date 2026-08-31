from datetime import datetime, timedelta, timezone

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


def _iso(dt: datetime) -> str:
    return dt.isoformat()


async def test_create_and_list_event(client, alice):
    await _login(client, "alice@example.com")
    start = datetime.now(timezone.utc) + timedelta(days=3)

    resp = await client.post(
        "/api/events",
        json={
            "title": "Dinner party",
            "event_type": "dinner",
            "location": "Kitchen",
            "start_at": _iso(start),
        },
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["title"] == "Dinner party"
    assert body["event_type"] == "dinner"
    assert body["rsvps"] == []

    listing = await client.get("/api/events")
    assert listing.status_code == 200
    assert len(listing.json()) == 1


async def test_rsvp_upsert(client, alice, test_engine):
    bob = await _create_user(test_engine, "bob@example.com", "Bob")
    await _login(client, "alice@example.com")
    start = datetime.now(timezone.utc) + timedelta(days=1)
    create_resp = await client.post(
        "/api/events", json={"title": "Game night", "start_at": _iso(start)}
    )
    event_id = create_resp.json()["id"]

    rsvp1 = await client.put(f"/api/events/{event_id}/rsvp", json={"status": "maybe"})
    assert rsvp1.status_code == 200
    assert rsvp1.json()["rsvps"] == [{"user_id": str(alice.id), "status": "maybe", "responded_at": rsvp1.json()["rsvps"][0]["responded_at"]}]

    # Changing your mind updates the same row rather than adding a second one.
    rsvp2 = await client.put(f"/api/events/{event_id}/rsvp", json={"status": "yes"})
    assert len(rsvp2.json()["rsvps"]) == 1
    assert rsvp2.json()["rsvps"][0]["status"] == "yes"

    await client.post("/api/auth/logout")
    await _login(client, "bob@example.com")
    rsvp3 = await client.put(f"/api/events/{event_id}/rsvp", json={"status": "no"})
    statuses = {r["user_id"]: r["status"] for r in rsvp3.json()["rsvps"]}
    assert statuses == {str(alice.id): "yes", str(bob.id): "no"}


async def test_event_series_grouping(client, alice):
    await _login(client, "alice@example.com")
    series_resp = await client.post(
        "/api/events/series", json={"name": "MasterChef Dinners", "description": "Cook-off series"}
    )
    assert series_resp.status_code == 201
    series_id = series_resp.json()["id"]

    start = datetime.now(timezone.utc) + timedelta(days=1)
    for i in range(3):
        resp = await client.post(
            "/api/events",
            json={
                "title": f"Round {i + 1}",
                "start_at": _iso(start + timedelta(days=7 * i)),
                "series_id": series_id,
            },
        )
        assert resp.status_code == 201

    filtered = await client.get("/api/events", params={"series_id": series_id})
    assert len(filtered.json()) == 3
    assert all(e["series_id"] == series_id for e in filtered.json())


async def test_update_and_delete_event(client, alice):
    await _login(client, "alice@example.com")
    start = datetime.now(timezone.utc) + timedelta(days=1)
    create_resp = await client.post("/api/events", json={"title": "Original", "start_at": _iso(start)})
    event_id = create_resp.json()["id"]

    updated = await client.patch(f"/api/events/{event_id}", json={"title": "Renamed"})
    assert updated.json()["title"] == "Renamed"

    deleted = await client.delete(f"/api/events/{event_id}")
    assert deleted.status_code == 204

    listing = await client.get("/api/events")
    assert listing.json() == []
