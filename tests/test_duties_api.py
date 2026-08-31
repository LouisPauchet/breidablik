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
