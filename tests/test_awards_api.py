from datetime import date

from fastapi_users.db import SQLAlchemyUserDatabase
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.auth.users import UserManager
from app.models.user import User
from app.schemas.user import UserCreate
from app.services.awards import _voting_start_day

CYCLE_MONTH = date(2026, 3, 1)
VOTING_START_DAY = _voting_start_day(CYCLE_MONTH.year, CYCLE_MONTH.month)


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


async def test_summary_requires_auth(client):
    resp = await client.get("/api/awards/summary")
    assert resp.status_code == 401


async def test_admin_tick_rejects_non_superuser(client, alice, test_engine):
    bob = await _create_user(test_engine, "bob@example.com", "Bob", is_superuser=False)
    await _login(client, "bob@example.com")
    resp = await client.post("/api/awards/admin/tick", json={"as_of": CYCLE_MONTH.isoformat()})
    assert resp.status_code == 403


async def test_summary_reflects_suggestion_window(client, alice):
    await _login(client, "alice@example.com")
    await _tick(client, date(CYCLE_MONTH.year, CYCLE_MONTH.month, 15))

    resp = await client.get("/api/awards/summary")
    assert resp.status_code == 200
    body = resp.json()
    assert body["current"]["phase"] == "suggesting"
    assert body["current"]["my_suggestion_submitted"] is False


async def test_suggest_rejected_outside_suggestion_window(client, alice):
    await _login(client, "alice@example.com")
    resp = await client.post("/api/awards/suggestions", json={"title": "Best Cook", "emoji": "🍳"})
    assert resp.status_code == 400


async def test_suggest_then_duplicate_rejected(client, alice):
    await _login(client, "alice@example.com")
    await _tick(client, date(CYCLE_MONTH.year, CYCLE_MONTH.month, 15))

    first = await client.post("/api/awards/suggestions", json={"title": "Best Cook", "emoji": "🍳"})
    assert first.status_code == 201

    second = await client.post("/api/awards/suggestions", json={"title": "Tidiest Room", "emoji": "🧹"})
    assert second.status_code == 409

    summary = await client.get("/api/awards/summary")
    assert summary.json()["current"]["my_suggestion_submitted"] is True


async def test_vote_rejected_before_voting_window(client, alice, test_engine):
    bob = await _create_user(test_engine, "bob@example.com", "Bob")
    await _login(client, "alice@example.com")
    await _tick(client, date(CYCLE_MONTH.year, CYCLE_MONTH.month, 15))

    summary = await client.get("/api/awards/summary")
    cycle_id = summary.json()["current"]["id"]

    resp = await client.put(f"/api/awards/cycles/{cycle_id}/vote", json={"candidate_user_id": str(bob.id)})
    assert resp.status_code == 400


async def test_vote_upsert_and_veto_flow(client, alice, test_engine):
    bob = await _create_user(test_engine, "bob@example.com", "Bob")
    carol = await _create_user(test_engine, "carol@example.com", "Carol")

    await _login(client, "alice@example.com")
    await _tick(client, date(CYCLE_MONTH.year, CYCLE_MONTH.month, 15))
    await client.post("/api/awards/suggestions", json={"title": "Best Cook", "emoji": "🍳"})
    await _tick(client, date(CYCLE_MONTH.year, CYCLE_MONTH.month, VOTING_START_DAY))

    summary = await client.get("/api/awards/summary")
    current = summary.json()["current"]
    assert current["phase"] == "voting"
    assert current["drawn_category_title"] == "Best Cook"
    cycle_id = current["id"]

    # Upsert: voting for Bob then changing to Carol leaves exactly one vote for Alice.
    r1 = await client.put(f"/api/awards/cycles/{cycle_id}/vote", json={"candidate_user_id": str(bob.id)})
    assert r1.status_code == 200
    r2 = await client.put(f"/api/awards/cycles/{cycle_id}/vote", json={"candidate_user_id": str(carol.id)})
    assert r2.status_code == 200

    summary2 = await client.get("/api/awards/summary")
    current2 = summary2.json()["current"]
    assert current2["my_vote_candidate_id"] == str(carol.id)
    tally = {v["candidate_user_id"]: v["vote_count"] for v in current2["votes"]}
    assert tally == {str(carol.id): 1}

    # Voting for a non-existent/inactive user is rejected.
    bad_vote = await client.put(
        f"/api/awards/cycles/{cycle_id}/vote", json={"candidate_user_id": "00000000-0000-0000-0000-000000000000"}
    )
    assert bad_vote.status_code == 422

    # Veto the drawn category (admin-only) right here in the voting phase, before reveal.
    veto = await client.post(f"/api/awards/cycles/{cycle_id}/veto", json={"reason": "inside joke"})
    assert veto.status_code == 200

    veto_again = await client.post(f"/api/awards/cycles/{cycle_id}/veto", json={})
    assert veto_again.status_code == 400

    await _tick(client, date(2026, 4, 7))  # first Saturday of April 2026 -> reveal

    final = await client.get("/api/awards/summary")
    decided = final.json()["latest_decided"]
    assert decided["community_award_vetoed"] is True
    assert decided["community_award_winner_id"] is None


async def test_veto_rejects_non_superuser(client, alice, test_engine):
    bob = await _create_user(test_engine, "bob@example.com", "Bob", is_superuser=False)
    await _login(client, "alice@example.com")
    await _tick(client, date(CYCLE_MONTH.year, CYCLE_MONTH.month, 15))
    await client.post("/api/awards/suggestions", json={"title": "Best Cook", "emoji": "🍳"})
    await _tick(client, date(CYCLE_MONTH.year, CYCLE_MONTH.month, VOTING_START_DAY))
    summary = await client.get("/api/awards/summary")
    cycle_id = summary.json()["current"]["id"]

    await client.post("/api/auth/logout")
    await _login(client, "bob@example.com")
    resp = await client.post(f"/api/awards/cycles/{cycle_id}/veto", json={})
    assert resp.status_code == 403


async def test_veto_rejects_when_nothing_drawn_yet(client, alice):
    await _login(client, "alice@example.com")
    await _tick(client, date(CYCLE_MONTH.year, CYCLE_MONTH.month, 15))
    summary = await client.get("/api/awards/summary")
    cycle_id = summary.json()["current"]["id"]

    resp = await client.post(f"/api/awards/cycles/{cycle_id}/veto", json={})
    assert resp.status_code == 400


async def test_member_history_lists_duty_master_and_community_badges(client, alice, test_engine):
    bob = await _create_user(test_engine, "bob@example.com", "Bob")

    await _login(client, "alice@example.com")
    await _tick(client, date(CYCLE_MONTH.year, CYCLE_MONTH.month, 15))
    await client.post("/api/awards/suggestions", json={"title": "Best Cook", "emoji": "🍳"})
    await _tick(client, date(CYCLE_MONTH.year, CYCLE_MONTH.month, VOTING_START_DAY))

    summary = await client.get("/api/awards/summary")
    cycle_id = summary.json()["current"]["id"]
    await client.put(f"/api/awards/cycles/{cycle_id}/vote", json={"candidate_user_id": str(bob.id)})

    await _tick(client, date(2026, 4, 7))

    history = await client.get(f"/api/awards/members/{bob.id}/history")
    assert history.status_code == 200
    badges = history.json()["badges"]
    assert any(b["kind"] == "community" and b["title"] == "Best Cook" for b in badges)
