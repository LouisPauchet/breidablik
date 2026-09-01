from datetime import date

from app.services.auto_reassign import pick_reassignment


def test_pick_reassignment_skips_to_next_available():
    candidates = [1, 2, 3]
    assert pick_reassignment(candidates, absent_user_id=1, away_user_ids_on_date=set()) == 2


def test_pick_reassignment_skips_someone_also_away():
    candidates = [1, 2, 3]
    assert pick_reassignment(candidates, absent_user_id=1, away_user_ids_on_date={2}) == 3


def test_pick_reassignment_wraps_around():
    candidates = [1, 2, 3]
    assert pick_reassignment(candidates, absent_user_id=3, away_user_ids_on_date=set()) == 1


def test_pick_reassignment_none_when_everyone_else_away():
    candidates = [1, 2, 3]
    assert pick_reassignment(candidates, absent_user_id=1, away_user_ids_on_date={2, 3}) is None


def test_pick_reassignment_none_for_single_person_rotation():
    assert pick_reassignment([1], absent_user_id=1, away_user_ids_on_date=set()) is None


def test_pick_reassignment_none_when_absent_user_not_a_candidate():
    assert pick_reassignment([1, 2], absent_user_id=99, away_user_ids_on_date=set()) is None


async def _login(client, email: str):
    resp = await client.post(
        "/api/auth/login", json={"email": email, "password": "correcthorsebatterystaple"}
    )
    assert resp.status_code == 200


async def _create_user(test_engine, email: str, display_name: str):
    from fastapi_users.db import SQLAlchemyUserDatabase
    from sqlalchemy.ext.asyncio import async_sessionmaker

    from app.auth.users import UserManager
    from app.models.user import User
    from app.schemas.user import UserCreate

    maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with maker() as session:
        manager = UserManager(SQLAlchemyUserDatabase(session, User))
        return await manager.create(
            UserCreate(email=email, password="correcthorsebatterystaple", display_name=display_name),
            safe=False,
        )


async def test_auto_reassign_swaps_already_materialized_occurrence(client, alice, test_engine):
    bob = await _create_user(test_engine, "bob@example.com", "Bob")
    await _login(client, "alice@example.com")

    today = date.today()
    create_resp = await client.post(
        "/api/duties",
        json={
            "title": "Bathroom",
            "start_date": today.isoformat(),
            "task_interval_days": 7,
            "rotation_interval_days": 14,
            "assignee_user_ids": [str(alice.id), str(bob.id)],
        },
    )
    duty_id = create_resp.json()["id"]

    detail = await client.get(f"/api/duties/{duty_id}")
    first = detail.json()["occurrences"][0]
    assert first["assigned_user_id"] == str(alice.id)
    assert first["is_manual_override"] is False

    absence_resp = await client.post(
        "/api/absences",
        json={
            "start_date": today.isoformat(),
            "end_date": today.isoformat(),
            "auto_reassign": True,
        },
    )
    assert absence_resp.status_code == 201

    detail_after = await client.get(f"/api/duties/{duty_id}")
    first_after = detail_after.json()["occurrences"][0]
    assert first_after["assigned_user_id"] == str(bob.id)
    assert first_after["is_manual_override"] is True


async def test_absence_without_auto_reassign_leaves_occurrence_assigned(client, alice, test_engine):
    bob = await _create_user(test_engine, "bob@example.com", "Bob")
    await _login(client, "alice@example.com")

    today = date.today()
    create_resp = await client.post(
        "/api/duties",
        json={
            "title": "Bathroom",
            "start_date": today.isoformat(),
            "task_interval_days": 7,
            "rotation_interval_days": 14,
            "assignee_user_ids": [str(alice.id), str(bob.id)],
        },
    )
    duty_id = create_resp.json()["id"]
    await client.get(f"/api/duties/{duty_id}")  # materialize

    await client.post(
        "/api/absences",
        json={"start_date": today.isoformat(), "end_date": today.isoformat()},
    )

    detail = await client.get(f"/api/duties/{duty_id}")
    first = detail.json()["occurrences"][0]
    assert first["assigned_user_id"] == str(alice.id)
    assert first["assignee_away"] is True


async def test_auto_reassign_applies_to_occurrences_materialized_later(client, alice, test_engine):
    bob = await _create_user(test_engine, "bob@example.com", "Bob")
    await _login(client, "alice@example.com")

    today = date.today()
    # The absence exists *before* the duty's occurrences are ever materialized.
    await client.post(
        "/api/absences",
        json={
            "start_date": today.isoformat(),
            "end_date": today.isoformat(),
            "auto_reassign": True,
        },
    )

    create_resp = await client.post(
        "/api/duties",
        json={
            "title": "Bathroom",
            "start_date": today.isoformat(),
            "task_interval_days": 7,
            "rotation_interval_days": 14,
            "assignee_user_ids": [str(alice.id), str(bob.id)],
        },
    )
    duty_id = create_resp.json()["id"]

    detail = await client.get(f"/api/duties/{duty_id}")
    first = detail.json()["occurrences"][0]
    assert first["assigned_user_id"] == str(bob.id)
    assert first["is_manual_override"] is True
