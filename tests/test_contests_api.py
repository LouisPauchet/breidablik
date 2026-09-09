from datetime import date

from fastapi_users.db import SQLAlchemyUserDatabase
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.auth.users import UserManager
from app.models.user import User
from app.schemas.user import UserCreate
from app.services.awards import _reveal_date

CYCLE_MONTH = date(2026, 3, 1)


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


async def _tick(client, as_of: date):
    resp = await client.post("/api/awards/admin/tick", json={"as_of": as_of.isoformat()})
    assert resp.status_code == 200


async def test_create_contest_succeeds_for_plain_member(client, alice, test_engine):
    bob = await _create_user(test_engine, "bob@example.com", "Bob", is_superuser=False)
    await _login(client, "bob@example.com")
    resp = await client.post(
        "/api/contests", json={"title": "Dishwasher", "description": None, "icon": "🍽️"}
    )
    assert resp.status_code == 201
    assert resp.json()["title"] == "Dishwasher"
    assert resp.json()["created_by_id"] == str(bob.id)


async def test_log_completion_updates_tally(client, alice, test_engine):
    bob = await _create_user(test_engine, "bob@example.com", "Bob")
    await _login(client, "alice@example.com")
    create_resp = await client.post("/api/contests", json={"title": "Dishwasher", "icon": "🍽️"})
    contest_id = create_resp.json()["id"]

    await client.post(f"/api/contests/{contest_id}/log")
    await client.post(f"/api/contests/{contest_id}/log")

    await client.post("/api/auth/logout")
    await _login(client, "bob@example.com")
    await client.post(f"/api/contests/{contest_id}/log")

    listing = await client.get("/api/contests")
    contest = next(c for c in listing.json() if c["id"] == contest_id)
    tally = {row["user_id"]: row["count"] for row in contest["tally"]}
    assert tally[str(alice.id)] == 2
    assert tally[str(bob.id)] == 1


async def test_delete_log_entry_own_only(client, alice, test_engine):
    bob = await _create_user(test_engine, "bob@example.com", "Bob", is_superuser=False)
    carol = await _create_user(test_engine, "carol@example.com", "Carol", is_superuser=False)
    await _login(client, "alice@example.com")
    create_resp = await client.post("/api/contests", json={"title": "Dishwasher", "icon": "🍽️"})
    contest_id = create_resp.json()["id"]

    await client.post("/api/auth/logout")
    await _login(client, "bob@example.com")
    log_resp = await client.post(f"/api/contests/{contest_id}/log")
    entry_id = log_resp.json()["id"]

    # Carol (a different non-superuser member) can't delete Bob's entry.
    await client.post("/api/auth/logout")
    await _login(client, "carol@example.com")
    forbidden = await client.delete(f"/api/contests/{contest_id}/log/{entry_id}")
    assert forbidden.status_code == 403

    # Bob can delete his own.
    await client.post("/api/auth/logout")
    await _login(client, "bob@example.com")
    ok = await client.delete(f"/api/contests/{contest_id}/log/{entry_id}")
    assert ok.status_code == 204

    # A superuser (Alice) can delete someone else's — log one more from Bob to test this.
    await client.post("/api/auth/logout")
    await _login(client, "bob@example.com")
    log_resp2 = await client.post(f"/api/contests/{contest_id}/log")
    entry_id2 = log_resp2.json()["id"]

    await client.post("/api/auth/logout")
    await _login(client, "alice@example.com")
    ok2 = await client.delete(f"/api/contests/{contest_id}/log/{entry_id2}")
    assert ok2.status_code == 204


async def test_contest_reveal_flow_end_to_end(client, alice, test_engine):
    bob = await _create_user(test_engine, "bob@example.com", "Bob")
    await _login(client, "alice@example.com")
    create_resp = await client.post("/api/contests", json={"title": "Dishwasher", "icon": "🍽️"})
    contest_id = create_resp.json()["id"]

    # Alice logs twice, Bob logs once -> Alice should win.
    await client.post(f"/api/contests/{contest_id}/log")
    await client.post(f"/api/contests/{contest_id}/log")

    await client.post("/api/auth/logout")
    await _login(client, "bob@example.com")
    await client.post(f"/api/contests/{contest_id}/log")

    await client.post("/api/auth/logout")
    await _login(client, "alice@example.com")

    # The log entries above were timestamped via the API's real "now" (ContestLogEntry has
    # no explicit logged_at override), so the cycle driven here must be for the real current
    # month, not the fixed CYCLE_MONTH the other tests in this file use for admin/tick calls.
    real_month = date(date.today().year, date.today().month, 1)
    await _tick(client, date(real_month.year, real_month.month, 15))
    await _tick(client, _reveal_date(real_month))

    summary = await client.get("/api/awards/summary")
    contest_results = summary.json()["latest_decided"]["contest_results"]
    assert len(contest_results) == 1
    assert contest_results[0]["contest_duty_id"] == contest_id
    assert contest_results[0]["winner_id"] == str(alice.id)
    assert contest_results[0]["completion_count"] == 2
    assert contest_results[0]["title"] == "Dishwasher"
    assert contest_results[0]["icon"] == "🍽️"

    history = await client.get(f"/api/awards/members/{alice.id}/history")
    badges = history.json()["badges"]
    assert any(b["kind"] == "contest" and b["title"] == "Dishwasher" for b in badges)
