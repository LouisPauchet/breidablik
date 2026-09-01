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


async def test_create_team_and_attach_duties(client, alice, test_engine):
    bob = await _create_user(test_engine, "bob@example.com", "Bob")
    carol = await _create_user(test_engine, "carol@example.com", "Carol")
    await _login(client, "alice@example.com")

    start = date.today()
    team_resp = await client.post(
        "/api/duty-teams",
        json={
            "name": "Cleaning Team",
            "start_date": start.isoformat(),
            "rotation_interval_days": 14,
            "member_user_ids": [str(alice.id), str(bob.id), str(carol.id)],
        },
    )
    assert team_resp.status_code == 201
    team_id = team_resp.json()["id"]
    assert [m["user_id"] for m in team_resp.json()["members"]] == [str(alice.id), str(bob.id), str(carol.id)]

    for title in ["Bathroom", "Kitchen", "Living room"]:
        duty_resp = await client.post(
            "/api/duties",
            json={
                "title": title,
                "start_date": start.isoformat(),
                "task_interval_days": 7,
                "team_id": team_id,
            },
        )
        assert duty_resp.status_code == 201, duty_resp.json()
        assert duty_resp.json()["team_id"] == team_id
        assert duty_resp.json()["rotation_interval_days"] is None
        assert duty_resp.json()["assignees"] == []

    detail = await client.get(f"/api/duty-teams/{team_id}")
    assignments = {a["duty_title"]: a["assignee_user_id"] for a in detail.json()["current_assignments"]}
    assert assignments == {
        "Bathroom": str(alice.id),
        "Kitchen": str(bob.id),
        "Living room": str(carol.id),
    }


async def test_duty_without_team_requires_manual_rotation_fields(client, alice):
    await _login(client, "alice@example.com")
    resp = await client.post(
        "/api/duties",
        json={"title": "Orphan", "start_date": date.today().isoformat(), "task_interval_days": 7},
    )
    assert resp.status_code == 422


async def test_team_rotation_shifts_assignments_next_period(client, alice, test_engine):
    bob = await _create_user(test_engine, "bob@example.com", "Bob")
    carol = await _create_user(test_engine, "carol@example.com", "Carol")
    await _login(client, "alice@example.com")

    start = date.today() - timedelta(days=14)  # so "today" falls in period 1, not period 0
    team_resp = await client.post(
        "/api/duty-teams",
        json={
            "name": "Cleaning Team",
            "start_date": start.isoformat(),
            "rotation_interval_days": 14,
            "member_user_ids": [str(alice.id), str(bob.id), str(carol.id)],
        },
    )
    team_id = team_resp.json()["id"]

    duty_ids = []
    for title in ["Bathroom", "Kitchen", "Living room"]:
        duty_resp = await client.post(
            "/api/duties",
            json={
                "title": title,
                "start_date": start.isoformat(),
                "task_interval_days": 14,
                "team_id": team_id,
            },
        )
        duty_ids.append(duty_resp.json()["id"])

    # Materialize occurrences for the Bathroom duty across both periods and check the
    # assignee actually rotates from period 0 to period 1.
    detail = await client.get(f"/api/duties/{duty_ids[0]}")
    occurrences = sorted(detail.json()["occurrences"], key=lambda o: o["due_date"])
    assert len(occurrences) >= 2
    assert occurrences[0]["period_index"] == 0
    assert occurrences[1]["period_index"] == 1
    assert occurrences[0]["assigned_user_id"] != occurrences[1]["assigned_user_id"]
    assert occurrences[0]["assigned_user_id"] == str(alice.id)
    assert occurrences[1]["assigned_user_id"] == str(bob.id)


async def test_team_override_swaps_a_period_for_one_duty(client, alice, test_engine):
    bob = await _create_user(test_engine, "bob@example.com", "Bob")
    await _login(client, "alice@example.com")

    start = date.today()
    team_resp = await client.post(
        "/api/duty-teams",
        json={
            "name": "Team",
            "start_date": start.isoformat(),
            "rotation_interval_days": 14,
            "member_user_ids": [str(alice.id), str(bob.id)],
        },
    )
    team_id = team_resp.json()["id"]
    duty_resp = await client.post(
        "/api/duties",
        json={"title": "Bathroom", "start_date": start.isoformat(), "task_interval_days": 7, "team_id": team_id},
    )
    duty_id = duty_resp.json()["id"]

    override_resp = await client.post(
        f"/api/duties/{duty_id}/overrides",
        json={"period_index": 0, "assignee_user_id": str(bob.id), "reason": "Alice is busy"},
    )
    assert override_resp.status_code == 201

    updated_duty = await client.get(f"/api/duties/{duty_id}")
    assert updated_duty.json()["current_period"]["assignee_user_id"] == str(bob.id)


async def test_update_team_members_reshuffles_assignments(client, alice, test_engine):
    bob = await _create_user(test_engine, "bob@example.com", "Bob")
    dave = await _create_user(test_engine, "dave@example.com", "Dave")
    await _login(client, "alice@example.com")

    start = date.today()
    team_resp = await client.post(
        "/api/duty-teams",
        json={
            "name": "Team",
            "start_date": start.isoformat(),
            "rotation_interval_days": 14,
            "member_user_ids": [str(alice.id), str(bob.id)],
        },
    )
    team_id = team_resp.json()["id"]

    updated = await client.patch(
        f"/api/duty-teams/{team_id}", json={"member_user_ids": [str(bob.id), str(dave.id)]}
    )
    assert updated.status_code == 200
    assert [m["user_id"] for m in updated.json()["members"]] == [str(bob.id), str(dave.id)]


async def test_adding_member_redispatches_pending_occurrences(client, alice, test_engine):
    bob = await _create_user(test_engine, "bob@example.com", "Bob")
    carol = await _create_user(test_engine, "carol@example.com", "Carol")
    await _login(client, "alice@example.com")

    start = date.today()
    team_resp = await client.post(
        "/api/duty-teams",
        json={
            "name": "Team",
            "start_date": start.isoformat(),
            "rotation_interval_days": 7,
            "member_user_ids": [str(alice.id), str(bob.id)],
        },
    )
    team_id = team_resp.json()["id"]
    duty_resp = await client.post(
        "/api/duties",
        json={"title": "Bathroom", "start_date": start.isoformat(), "task_interval_days": 7, "team_id": team_id},
    )
    duty_id = duty_resp.json()["id"]

    # Materialize under the 2-person roster: alternates alice/bob, never carol.
    before = await client.get(f"/api/duties/{duty_id}")
    before_assignees = {o["assigned_user_id"] for o in before.json()["occurrences"]}
    assert before_assignees == {str(alice.id), str(bob.id)}

    add_carol = await client.patch(
        f"/api/duty-teams/{team_id}",
        json={"member_user_ids": [str(alice.id), str(bob.id), str(carol.id)]},
    )
    assert add_carol.status_code == 200

    after = await client.get(f"/api/duties/{duty_id}")
    after_assignees = {o["assigned_user_id"] for o in after.json()["occurrences"]}
    assert str(carol.id) in after_assignees


async def test_redispatch_does_not_touch_completed_occurrences(client, alice, test_engine):
    bob = await _create_user(test_engine, "bob@example.com", "Bob")
    carol = await _create_user(test_engine, "carol@example.com", "Carol")
    await _login(client, "alice@example.com")

    start = date.today()
    team_resp = await client.post(
        "/api/duty-teams",
        json={
            "name": "Team",
            "start_date": start.isoformat(),
            "rotation_interval_days": 7,
            "member_user_ids": [str(alice.id), str(bob.id)],
        },
    )
    team_id = team_resp.json()["id"]
    duty_resp = await client.post(
        "/api/duties",
        json={"title": "Bathroom", "start_date": start.isoformat(), "task_interval_days": 7, "team_id": team_id},
    )
    duty_id = duty_resp.json()["id"]

    detail = await client.get(f"/api/duties/{duty_id}")
    first_occurrence = detail.json()["occurrences"][0]
    assert first_occurrence["assigned_user_id"] == str(alice.id)

    done = await client.post(f"/api/duties/{duty_id}/occurrences/{first_occurrence['id']}/toggle-done")
    assert done.status_code == 200

    await client.patch(
        f"/api/duty-teams/{team_id}",
        json={"member_user_ids": [str(alice.id), str(bob.id), str(carol.id)]},
    )

    after = await client.get(f"/api/duties/{duty_id}")
    after_first = next(o for o in after.json()["occurrences"] if o["id"] == first_occurrence["id"])
    assert after_first["is_done"] is True
    assert after_first["assigned_user_id"] == str(alice.id)


async def test_redispatch_does_not_touch_manually_reassigned_occurrences(client, alice, test_engine):
    bob = await _create_user(test_engine, "bob@example.com", "Bob")
    carol = await _create_user(test_engine, "carol@example.com", "Carol")
    await _login(client, "alice@example.com")

    start = date.today()
    team_resp = await client.post(
        "/api/duty-teams",
        json={
            "name": "Team",
            "start_date": start.isoformat(),
            "rotation_interval_days": 7,
            "member_user_ids": [str(alice.id), str(bob.id)],
        },
    )
    team_id = team_resp.json()["id"]
    duty_resp = await client.post(
        "/api/duties",
        json={"title": "Bathroom", "start_date": start.isoformat(), "task_interval_days": 7, "team_id": team_id},
    )
    duty_id = duty_resp.json()["id"]

    detail = await client.get(f"/api/duties/{duty_id}")
    first_occurrence = detail.json()["occurrences"][0]
    assert first_occurrence["assigned_user_id"] == str(alice.id)

    # Alice manually hands her occurrence off to Bob (e.g. she's away that day).
    swap = await client.patch(
        f"/api/duties/{duty_id}/occurrences/{first_occurrence['id']}",
        json={"assigned_user_id": str(bob.id)},
    )
    assert swap.status_code == 200

    await client.patch(
        f"/api/duty-teams/{team_id}",
        json={"member_user_ids": [str(alice.id), str(bob.id), str(carol.id)]},
    )

    after = await client.get(f"/api/duties/{duty_id}")
    after_first = next(o for o in after.json()["occurrences"] if o["id"] == first_occurrence["id"])
    assert after_first["is_manual_override"] is True
    assert after_first["assigned_user_id"] == str(bob.id)


async def test_deleting_team_cascades_to_duties(client, alice):
    await _login(client, "alice@example.com")
    start = date.today()
    team_resp = await client.post(
        "/api/duty-teams",
        json={
            "name": "Team",
            "start_date": start.isoformat(),
            "rotation_interval_days": 14,
            "member_user_ids": [str(alice.id)],
        },
    )
    team_id = team_resp.json()["id"]
    duty_resp = await client.post(
        "/api/duties",
        json={"title": "Bathroom", "start_date": start.isoformat(), "task_interval_days": 7, "team_id": team_id},
    )
    duty_id = duty_resp.json()["id"]

    delete_resp = await client.delete(f"/api/duty-teams/{team_id}")
    assert delete_resp.status_code == 204

    missing = await client.get(f"/api/duties/{duty_id}")
    assert missing.status_code == 404


async def test_on_duty_today_includes_team_duties(client, alice, test_engine):
    bob = await _create_user(test_engine, "bob@example.com", "Bob")
    await _login(client, "alice@example.com")
    start = date.today()
    team_resp = await client.post(
        "/api/duty-teams",
        json={
            "name": "Team",
            "start_date": start.isoformat(),
            "rotation_interval_days": 14,
            "member_user_ids": [str(alice.id), str(bob.id)],
        },
    )
    team_id = team_resp.json()["id"]
    await client.post(
        "/api/duties",
        json={"title": "Bathroom", "start_date": start.isoformat(), "task_interval_days": 7, "team_id": team_id},
    )

    resp = await client.get("/api/duties/on-duty-today")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert body[0]["duty_title"] == "Bathroom"
    assert body[0]["assignee_user_id"] == str(alice.id)
