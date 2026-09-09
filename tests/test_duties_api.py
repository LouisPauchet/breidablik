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
    return resp


async def test_create_duty_and_read_current_period(client, alice, test_engine):
    bob = await _create_user(test_engine, "bob@example.com", "Bob")
    await _login(client, "alice@example.com")

    start = date.today() - timedelta(days=1)
    resp = await client.post(
        "/api/duties",
        json={
            "title": "Bathroom",
            "start_date": start.isoformat(),
            "task_interval_days": 7,
            "rotation_interval_days": 14,
            "assignee_user_ids": [str(alice.id), str(bob.id)],
        },
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["title"] == "Bathroom"
    assert [a["user_id"] for a in body["assignees"]] == [str(alice.id), str(bob.id)]
    # start_date was yesterday, rotation is 14 days -> still period 0 -> Alice (first in order).
    assert body["current_period"]["period_index"] == 0
    assert body["current_period"]["assignee_user_id"] == str(alice.id)


async def test_duty_detail_materializes_occurrences(client, alice, test_engine):
    bob = await _create_user(test_engine, "bob@example.com", "Bob")
    await _login(client, "alice@example.com")

    start = date.today()
    create_resp = await client.post(
        "/api/duties",
        json={
            "title": "Bathroom",
            "start_date": start.isoformat(),
            "task_interval_days": 7,
            "rotation_interval_days": 14,
            "assignee_user_ids": [str(alice.id), str(bob.id)],
        },
    )
    duty_id = create_resp.json()["id"]

    detail = await client.get(f"/api/duties/{duty_id}")
    assert detail.status_code == 200
    occurrences = detail.json()["occurrences"]
    assert len(occurrences) >= 8  # 56-day default horizon / 7-day task interval
    assert occurrences[0]["due_date"] == start.isoformat()
    assert occurrences[0]["assigned_user_id"] == str(alice.id)
    # Second occurrence (day 7) is still period 0 (rotation every 14 days) -> still Alice.
    assert occurrences[1]["assigned_user_id"] == str(alice.id)
    # Third occurrence (day 14) crosses into period 1 -> Bob.
    assert occurrences[2]["assigned_user_id"] == str(bob.id)

    # Calling detail again must not duplicate rows (idempotent materialization).
    detail2 = await client.get(f"/api/duties/{duty_id}")
    assert len(detail2.json()["occurrences"]) == len(occurrences)


async def test_override_affects_future_materialization_not_past_rows(client, alice, test_engine):
    bob = await _create_user(test_engine, "bob@example.com", "Bob")
    await _login(client, "alice@example.com")

    start = date.today()
    create_resp = await client.post(
        "/api/duties",
        json={
            "title": "Bathroom",
            "start_date": start.isoformat(),
            "task_interval_days": 7,
            "rotation_interval_days": 14,
            "assignee_user_ids": [str(alice.id), str(bob.id)],
        },
    )
    duty_id = create_resp.json()["id"]

    # Materialize once (period 0 -> Alice, period 1 -> Bob, ...).
    await client.get(f"/api/duties/{duty_id}")

    # Swap period 1 (Bob's turn) to Alice, before any period-1 occurrence exists yet in a
    # fresh duty — but here occurrences already exist from the call above, so this exercises
    # the "override doesn't retroactively rewrite already-materialized rows" behavior.
    override_resp = await client.post(
        f"/api/duties/{duty_id}/overrides",
        json={"period_index": 1, "assignee_user_id": str(alice.id), "reason": "Bob is busy"},
    )
    assert override_resp.status_code == 201

    detail = await client.get(f"/api/duties/{duty_id}")
    occurrences = detail.json()["occurrences"]
    period_1_occurrence = next(o for o in occurrences if o["period_index"] == 1)
    # Not retroactively changed by the override alone.
    assert period_1_occurrence["assigned_user_id"] == str(bob.id)

    # Directly reassigning that occurrence is the correct way to swap an existing row.
    reassign = await client.patch(
        f"/api/duties/{duty_id}/occurrences/{period_1_occurrence['id']}",
        json={"assigned_user_id": str(alice.id)},
    )
    assert reassign.status_code == 200
    assert reassign.json()["is_manual_override"] is True
    assert reassign.json()["assigned_user_id"] == str(alice.id)


async def test_toggle_occurrence_done(client, alice, test_engine):
    await _login(client, "alice@example.com")
    start = date.today()
    create_resp = await client.post(
        "/api/duties",
        json={
            "title": "Bathroom",
            "start_date": start.isoformat(),
            "task_interval_days": 7,
            "rotation_interval_days": 7,
            "assignee_user_ids": [str(alice.id)],
        },
    )
    duty_id = create_resp.json()["id"]
    detail = await client.get(f"/api/duties/{duty_id}")
    occurrence_id = detail.json()["occurrences"][0]["id"]

    toggled = await client.post(f"/api/duties/{duty_id}/occurrences/{occurrence_id}/toggle-done")
    assert toggled.status_code == 200
    assert toggled.json()["is_done"] is True
    assert toggled.json()["done_by_id"] == str(alice.id)

    toggled_back = await client.post(f"/api/duties/{duty_id}/occurrences/{occurrence_id}/toggle-done")
    assert toggled_back.json()["is_done"] is False
    assert toggled_back.json()["done_by_id"] is None


async def test_occurrence_flags_assignee_away(client, alice, test_engine):
    bob = await _create_user(test_engine, "bob@example.com", "Bob")
    await _login(client, "alice@example.com")

    start = date.today()
    create_resp = await client.post(
        "/api/duties",
        json={
            "title": "Bathroom",
            "start_date": start.isoformat(),
            "task_interval_days": 7,
            "rotation_interval_days": 7,
            "assignee_user_ids": [str(alice.id), str(bob.id)],
        },
    )
    duty_id = create_resp.json()["id"]

    # Alice is on duty today (period 0); mark her away for that window.
    away_start = start.isoformat()
    away_end = (start + timedelta(days=3)).isoformat()
    await client.post("/api/absences", json={"start_date": away_start, "end_date": away_end})

    detail = await client.get(f"/api/duties/{duty_id}")
    occurrences = detail.json()["occurrences"]
    assert occurrences[0]["assigned_user_id"] == str(alice.id)
    assert occurrences[0]["assignee_away"] is True
    # Bob's occurrence (period 1, a week later) is unaffected.
    assert occurrences[1]["assignee_away"] is False


async def test_on_duty_today_widget(client, alice, test_engine):
    bob = await _create_user(test_engine, "bob@example.com", "Bob")
    await _login(client, "alice@example.com")
    await client.post(
        "/api/duties",
        json={
            "title": "Bathroom",
            "start_date": date.today().isoformat(),
            "task_interval_days": 7,
            "rotation_interval_days": 14,
            "assignee_user_ids": [str(alice.id), str(bob.id)],
        },
    )
    resp = await client.get("/api/duties/on-duty-today")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert body[0]["duty_title"] == "Bathroom"
    assert body[0]["assignee_user_id"] == str(alice.id)


async def test_update_duty_reassigns_assignees(client, alice, test_engine):
    bob = await _create_user(test_engine, "bob@example.com", "Bob")
    await _login(client, "alice@example.com")
    create_resp = await client.post(
        "/api/duties",
        json={
            "title": "Bathroom",
            "start_date": date.today().isoformat(),
            "task_interval_days": 7,
            "rotation_interval_days": 7,
            "assignee_user_ids": [str(alice.id)],
        },
    )
    duty_id = create_resp.json()["id"]

    updated = await client.patch(
        f"/api/duties/{duty_id}", json={"assignee_user_ids": [str(bob.id)]}
    )
    assert updated.status_code == 200
    assert [a["user_id"] for a in updated.json()["assignees"]] == [str(bob.id)]


async def test_upcoming_occurrences_across_duties(client, alice, test_engine):
    bob = await _create_user(test_engine, "bob@example.com", "Bob")
    await _login(client, "alice@example.com")

    start = date.today()
    await client.post(
        "/api/duties",
        json={
            "title": "Bathroom",
            "start_date": start.isoformat(),
            "task_interval_days": 7,
            "rotation_interval_days": 7,
            "assignee_user_ids": [str(alice.id)],
        },
    )
    await client.post(
        "/api/duties",
        json={
            "title": "Kitchen",
            "start_date": start.isoformat(),
            "task_interval_days": 14,
            "rotation_interval_days": 14,
            "assignee_user_ids": [str(bob.id)],
        },
    )

    resp = await client.get("/api/duties/occurrences/upcoming")
    assert resp.status_code == 200
    body = resp.json()
    titles = {entry["duty_title"] for entry in body}
    assert titles == {"Bathroom", "Kitchen"}
    # Bathroom (7-day task interval) contributes more occurrences than Kitchen (14-day) over
    # the same horizon.
    bathroom_count = sum(1 for e in body if e["duty_title"] == "Bathroom")
    kitchen_count = sum(1 for e in body if e["duty_title"] == "Kitchen")
    assert bathroom_count > kitchen_count


async def test_upcoming_occurrences_empty_when_no_duties(client, alice):
    await _login(client, "alice@example.com")
    resp = await client.get("/api/duties/occurrences/upcoming")
    assert resp.status_code == 200
    assert resp.json() == []


async def test_toggle_occurrence_done_rejected_for_non_assignee(client, alice, test_engine):
    bob = await _create_user(test_engine, "bob@example.com", "Bob")
    carol = await _create_user(test_engine, "carol@example.com", "Carol")
    await _login(client, "alice@example.com")
    create_resp = await client.post(
        "/api/duties",
        json={
            "title": "Bathroom",
            "start_date": date.today().isoformat(),
            "task_interval_days": 7,
            "rotation_interval_days": 7,
            "assignee_user_ids": [str(bob.id)],
        },
    )
    duty_id = create_resp.json()["id"]
    detail = await client.get(f"/api/duties/{duty_id}")
    occurrence_id = detail.json()["occurrences"][0]["id"]

    await client.post("/api/auth/logout")
    await _login(client, "carol@example.com")
    resp = await client.post(f"/api/duties/{duty_id}/occurrences/{occurrence_id}/toggle-done")
    assert resp.status_code == 403


async def test_toggle_occurrence_done_allowed_for_assignee_non_superuser(client, alice, test_engine):
    bob = await _create_user(test_engine, "bob@example.com", "Bob")
    await _login(client, "alice@example.com")
    create_resp = await client.post(
        "/api/duties",
        json={
            "title": "Bathroom",
            "start_date": date.today().isoformat(),
            "task_interval_days": 7,
            "rotation_interval_days": 7,
            "assignee_user_ids": [str(bob.id)],
        },
    )
    duty_id = create_resp.json()["id"]
    detail = await client.get(f"/api/duties/{duty_id}")
    occurrence_id = detail.json()["occurrences"][0]["id"]

    await client.post("/api/auth/logout")
    await _login(client, "bob@example.com")
    resp = await client.post(f"/api/duties/{duty_id}/occurrences/{occurrence_id}/toggle-done")
    assert resp.status_code == 200
    assert resp.json()["is_done"] is True
    assert resp.json()["done_by_id"] == str(bob.id)


async def test_toggle_occurrence_done_allowed_for_superuser_non_assignee(client, alice, test_engine):
    bob = await _create_user(test_engine, "bob@example.com", "Bob")
    await _login(client, "alice@example.com")
    create_resp = await client.post(
        "/api/duties",
        json={
            "title": "Bathroom",
            "start_date": date.today().isoformat(),
            "task_interval_days": 7,
            "rotation_interval_days": 7,
            "assignee_user_ids": [str(bob.id)],
        },
    )
    duty_id = create_resp.json()["id"]
    detail = await client.get(f"/api/duties/{duty_id}")
    occurrence_id = detail.json()["occurrences"][0]["id"]

    # Alice (superuser) is not the assignee but can still toggle it.
    resp = await client.post(f"/api/duties/{duty_id}/occurrences/{occurrence_id}/toggle-done")
    assert resp.status_code == 200
    assert resp.json()["is_done"] is True


async def test_occurrence_status_hidden_from_non_assignee(client, alice, test_engine):
    bob = await _create_user(test_engine, "bob@example.com", "Bob")
    carol = await _create_user(test_engine, "carol@example.com", "Carol")
    await _login(client, "alice@example.com")
    create_resp = await client.post(
        "/api/duties",
        json={
            "title": "Bathroom",
            "start_date": date.today().isoformat(),
            "task_interval_days": 7,
            "rotation_interval_days": 7,
            "assignee_user_ids": [str(bob.id)],
        },
    )
    duty_id = create_resp.json()["id"]

    await client.post("/api/auth/logout")
    await _login(client, "carol@example.com")
    detail = await client.get(f"/api/duties/{duty_id}")
    occurrence = detail.json()["occurrences"][0]
    assert occurrence["is_done"] is None
    assert occurrence["done_by_id"] is None
    assert occurrence["done_at"] is None
    # Non-privacy fields (scheduling info) stay visible to everyone.
    assert occurrence["assigned_user_id"] == str(bob.id)
    assert occurrence["due_date"] == date.today().isoformat()


async def test_upcoming_occurrences_hides_status_for_non_assignee(client, alice, test_engine):
    bob = await _create_user(test_engine, "bob@example.com", "Bob")
    carol = await _create_user(test_engine, "carol@example.com", "Carol")
    await _login(client, "alice@example.com")
    await client.post(
        "/api/duties",
        json={
            "title": "Bathroom",
            "start_date": date.today().isoformat(),
            "task_interval_days": 7,
            "rotation_interval_days": 7,
            "assignee_user_ids": [str(bob.id)],
        },
    )

    await client.post("/api/auth/logout")
    await _login(client, "carol@example.com")
    resp = await client.get("/api/duties/occurrences/upcoming")
    assert resp.status_code == 200
    assert all(entry["is_done"] is None for entry in resp.json())


async def test_on_duty_today_exposes_occurrence_id_for_own_entry_only(client, alice, test_engine):
    bob = await _create_user(test_engine, "bob@example.com", "Bob")
    carol = await _create_user(test_engine, "carol@example.com", "Carol")
    await _login(client, "alice@example.com")
    await client.post(
        "/api/duties",
        json={
            "title": "Bathroom",
            "start_date": date.today().isoformat(),
            "task_interval_days": 7,
            "rotation_interval_days": 7,
            "assignee_user_ids": [str(bob.id)],
        },
    )
    await client.post(
        "/api/duties",
        json={
            "title": "Kitchen",
            "start_date": date.today().isoformat(),
            "task_interval_days": 7,
            "rotation_interval_days": 7,
            "assignee_user_ids": [str(carol.id)],
        },
    )

    await client.post("/api/auth/logout")
    await _login(client, "bob@example.com")
    resp = await client.get("/api/duties/on-duty-today")
    body = {entry["duty_title"]: entry for entry in resp.json()}
    assert body["Bathroom"]["occurrence_id"] is not None
    assert body["Bathroom"]["is_done"] is False
    assert body["Kitchen"]["occurrence_id"] is None
    assert body["Kitchen"]["is_done"] is None


async def test_occurrence_visible_and_toggleable_by_anyone_when_assignee_away(client, alice, test_engine):
    bob = await _create_user(test_engine, "bob@example.com", "Bob")
    carol = await _create_user(test_engine, "carol@example.com", "Carol")
    await _login(client, "alice@example.com")
    create_resp = await client.post(
        "/api/duties",
        json={
            "title": "Bathroom",
            "start_date": date.today().isoformat(),
            "task_interval_days": 7,
            "rotation_interval_days": 7,
            "assignee_user_ids": [str(bob.id)],
        },
    )
    duty_id = create_resp.json()["id"]
    detail = await client.get(f"/api/duties/{duty_id}")
    occurrence_id = detail.json()["occurrences"][0]["id"]

    # Mark Bob away for a window covering today, logged in as Bob himself (absences are
    # always created for the calling user).
    await client.post("/api/auth/logout")
    await _login(client, "bob@example.com")
    away_start = date.today().isoformat()
    away_end = (date.today() + timedelta(days=2)).isoformat()
    await client.post("/api/absences", json={"start_date": away_start, "end_date": away_end})

    # Carol, unrelated and non-superuser, can now see AND toggle Bob's occurrence.
    await client.post("/api/auth/logout")
    await _login(client, "carol@example.com")
    detail2 = await client.get(f"/api/duties/{duty_id}")
    occurrence = detail2.json()["occurrences"][0]
    assert occurrence["is_done"] is False  # visible, not hidden
    assert occurrence["assignee_away"] is True

    toggled = await client.post(f"/api/duties/{duty_id}/occurrences/{occurrence_id}/toggle-done")
    assert toggled.status_code == 200
    assert toggled.json()["is_done"] is True
    assert toggled.json()["done_by_id"] == str(carol.id)


async def test_on_duty_today_resolves_occurrence_for_others_when_assignee_away(client, alice, test_engine):
    bob = await _create_user(test_engine, "bob@example.com", "Bob")
    carol = await _create_user(test_engine, "carol@example.com", "Carol")
    await _login(client, "alice@example.com")
    await client.post(
        "/api/duties",
        json={
            "title": "Bathroom",
            "start_date": date.today().isoformat(),
            "task_interval_days": 7,
            "rotation_interval_days": 7,
            "assignee_user_ids": [str(bob.id)],
        },
    )

    await client.post("/api/auth/logout")
    await _login(client, "bob@example.com")
    away_start = date.today().isoformat()
    away_end = (date.today() + timedelta(days=2)).isoformat()
    await client.post("/api/absences", json={"start_date": away_start, "end_date": away_end})

    await client.post("/api/auth/logout")
    await _login(client, "carol@example.com")
    resp = await client.get("/api/duties/on-duty-today")
    body = {entry["duty_title"]: entry for entry in resp.json()}
    assert body["Bathroom"]["occurrence_id"] is not None
    assert body["Bathroom"]["is_done"] is False
