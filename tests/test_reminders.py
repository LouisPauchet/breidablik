import uuid
from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

import app.services.push as push_module
from app.models.duty import Duty, DutyAssignee, DutyOccurrence
from app.models.event import Event, EventRSVP, RSVPStatus
from app.models.notification import Notification
from app.models.task import Task, TaskAssignee
from app.models.user import User
from app.services.reminders import send_duty_reminders, send_event_reminders, send_task_reminders

ALICE = uuid.uuid4()
BOB = uuid.uuid4()


def _session(test_engine):
    return async_sessionmaker(test_engine, expire_on_commit=False)()


async def _seed_users(session, ids_and_names):
    for user_id, name in ids_and_names:
        session.add(
            User(
                id=user_id,
                email=f"{name.lower()}@example.com",
                hashed_password="x",
                display_name=name,
                is_active=True,
                is_superuser=False,
                is_verified=True,
            )
        )
    await session.commit()


async def _disable_real_push(monkeypatch):
    fake_settings = SimpleNamespace(vapid_private_key="", vapid_claim_email="mailto:test@example.com")
    monkeypatch.setattr(push_module, "get_settings", lambda: fake_settings)


async def test_event_reminder_notifies_everyone_except_declined(test_engine, monkeypatch):
    await _disable_real_push(monkeypatch)
    async with _session(test_engine) as session:
        await _seed_users(session, [(ALICE, "Alice"), (BOB, "Bob")])

        event = Event(
            title="Dinner",
            start_at=datetime.now(timezone.utc) + timedelta(hours=2),
            created_by_id=ALICE,
        )
        session.add(event)
        await session.flush()
        session.add(EventRSVP(event_id=event.id, user_id=BOB, status=RSVPStatus.no))
        await session.commit()

        await send_event_reminders(session)

        result = await session.execute(select(Notification))
        notifications = list(result.scalars())
        assert len(notifications) == 1
        assert notifications[0].user_id == ALICE
        assert notifications[0].kind == "event_reminder"

        await session.refresh(event)
        assert event.reminder_sent_at is not None


async def test_event_reminder_skips_events_outside_lead_window(test_engine, monkeypatch):
    await _disable_real_push(monkeypatch)
    async with _session(test_engine) as session:
        await _seed_users(session, [(ALICE, "Alice")])
        far_event = Event(
            title="Next month",
            start_at=datetime.now(timezone.utc) + timedelta(days=30),
            created_by_id=ALICE,
        )
        session.add(far_event)
        await session.commit()

        await send_event_reminders(session)

        result = await session.execute(select(Notification))
        assert list(result.scalars()) == []


async def test_event_reminder_is_idempotent(test_engine, monkeypatch):
    await _disable_real_push(monkeypatch)
    async with _session(test_engine) as session:
        await _seed_users(session, [(ALICE, "Alice")])
        event = Event(
            title="Dinner", start_at=datetime.now(timezone.utc) + timedelta(hours=1), created_by_id=ALICE
        )
        session.add(event)
        await session.commit()

        await send_event_reminders(session)
        await send_event_reminders(session)

        result = await session.execute(select(Notification))
        assert len(list(result.scalars())) == 1


async def test_duty_reminder_for_overdue_undone_occurrence(test_engine, monkeypatch):
    await _disable_real_push(monkeypatch)
    async with _session(test_engine) as session:
        await _seed_users(session, [(ALICE, "Alice")])
        duty = Duty(
            title="Bathroom",
            start_date=date.today() - timedelta(days=14),
            task_interval_days=7,
            rotation_interval_days=7,
            created_by_id=ALICE,
        )
        session.add(duty)
        await session.flush()
        session.add(DutyAssignee(duty_id=duty.id, user_id=ALICE, order_index=0))
        await session.commit()

        await send_duty_reminders(session)

        result = await session.execute(select(Notification))
        notifications = list(result.scalars())
        assert len(notifications) >= 1
        assert all(n.user_id == ALICE and n.kind == "duty_reminder" for n in notifications)


async def test_duty_reminder_skips_done_occurrence(test_engine, monkeypatch):
    await _disable_real_push(monkeypatch)
    async with _session(test_engine) as session:
        await _seed_users(session, [(ALICE, "Alice")])
        duty = Duty(
            title="Bathroom",
            start_date=date.today(),
            task_interval_days=7,
            rotation_interval_days=7,
            created_by_id=ALICE,
        )
        session.add(duty)
        await session.flush()
        session.add(DutyAssignee(duty_id=duty.id, user_id=ALICE, order_index=0))
        await session.commit()

        # Materialize today's occurrence and mark it done before reminders ever run.
        from app.services.occurrences import ensure_occurrences_materialized

        await ensure_occurrences_materialized(session, duty, date.today())
        occ_result = await session.execute(select(DutyOccurrence).where(DutyOccurrence.duty_id == duty.id))
        occurrence = occ_result.scalar_one()
        occurrence.is_done = True
        await session.commit()

        await send_duty_reminders(session)

        result = await session.execute(select(Notification))
        assert list(result.scalars()) == []


async def test_duty_reminder_is_idempotent(test_engine, monkeypatch):
    await _disable_real_push(monkeypatch)
    async with _session(test_engine) as session:
        await _seed_users(session, [(ALICE, "Alice")])
        duty = Duty(
            title="Bathroom",
            start_date=date.today(),
            task_interval_days=7,
            rotation_interval_days=7,
            created_by_id=ALICE,
        )
        session.add(duty)
        await session.flush()
        session.add(DutyAssignee(duty_id=duty.id, user_id=ALICE, order_index=0))
        await session.commit()

        await send_duty_reminders(session)
        count_after_first = len(list((await session.execute(select(Notification))).scalars()))

        await send_duty_reminders(session)
        count_after_second = len(list((await session.execute(select(Notification))).scalars()))

        assert count_after_first == count_after_second
        assert count_after_first >= 1


async def test_task_reminder_for_overdue_undone_task(test_engine, monkeypatch):
    await _disable_real_push(monkeypatch)
    async with _session(test_engine) as session:
        await _seed_users(session, [(ALICE, "Alice")])
        task = Task(title="Fix fence", due_date=date.today() - timedelta(days=1), created_by_id=ALICE)
        session.add(task)
        await session.flush()
        session.add(TaskAssignee(task_id=task.id, user_id=ALICE))
        await session.commit()

        await send_task_reminders(session)

        result = await session.execute(select(Notification))
        notifications = list(result.scalars())
        assert len(notifications) == 1
        assert notifications[0].user_id == ALICE
        assert notifications[0].kind == "task_reminder"


async def test_task_reminder_skips_task_without_due_date(test_engine, monkeypatch):
    await _disable_real_push(monkeypatch)
    async with _session(test_engine) as session:
        await _seed_users(session, [(ALICE, "Alice")])
        task = Task(title="Someday", due_date=None, created_by_id=ALICE)
        session.add(task)
        await session.flush()
        session.add(TaskAssignee(task_id=task.id, user_id=ALICE))
        await session.commit()

        await send_task_reminders(session)

        result = await session.execute(select(Notification))
        assert list(result.scalars()) == []
