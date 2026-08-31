"""Event-coming-soon and undone-duty/task reminders. Unlike the shopping-list push (purely
request-triggered), these genuinely need a time trigger even if nobody opens the app — see
app/routers/internal.py (Passenger: hit by the shared host's own cron) and the optional
in-process APScheduler wired in app/main.py (Docker only, since Passenger may recycle its
worker process and can't be trusted to keep a scheduler alive).

Each function is idempotent, guarded by a `reminder_sent_at` column on the row itself rather
than a separate log table — a tick can run as often as it likes without double-notifying.
"""

from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import get_settings
from app.models.duty import Duty, DutyOccurrence
from app.models.event import Event, RSVPStatus
from app.models.notification import Notification
from app.models.task import Task
from app.models.user import User
from app.services.occurrences import DEFAULT_HORIZON_DAYS, ensure_occurrences_materialized
from app.services.push import send_push_to_user
from app.timeutils import today

EVENT_REMINDER_LEAD = timedelta(hours=24)


async def send_event_reminders(session: AsyncSession) -> None:
    now = datetime.now(timezone.utc)
    window_end = now + EVENT_REMINDER_LEAD

    result = await session.execute(
        select(Event)
        .options(selectinload(Event.rsvps))
        .where(Event.reminder_sent_at.is_(None), Event.start_at > now, Event.start_at <= window_end)
    )
    events = list(result.scalars().unique())
    if not events:
        return

    users_result = await session.execute(select(User.id).where(User.is_active.is_(True)))
    active_user_ids = set(users_result.scalars())
    local_tz = get_settings().zone_info

    for event in events:
        declined = {r.user_id for r in event.rsvps if r.status == RSVPStatus.no}
        recipients = active_user_ids - declined
        local_start = event.start_at.astimezone(local_tz)
        title = f"Coming up: {event.title}"
        body = f"Starts {local_start.strftime('%a %H:%M')}"
        url = f"/events/{event.id}"

        for user_id in recipients:
            session.add(Notification(user_id=user_id, kind="event_reminder", title=title, body=body, url=url))
        event.reminder_sent_at = now
        await session.commit()

        for user_id in recipients:
            await send_push_to_user(session, user_id, {"title": title, "body": body, "url": url})


async def send_duty_reminders(session: AsyncSession) -> None:
    on_date = today()
    now = datetime.now(timezone.utc)

    duties_result = await session.execute(
        select(Duty)
        .options(selectinload(Duty.assignees), selectinload(Duty.overrides))
        .where(Duty.is_active.is_(True))
    )
    duties = list(duties_result.scalars().unique())
    duty_by_id = {d.id: d for d in duties}

    horizon = on_date + timedelta(days=DEFAULT_HORIZON_DAYS)
    for duty in duties:
        await ensure_occurrences_materialized(session, duty, horizon)

    result = await session.execute(
        select(DutyOccurrence).where(
            DutyOccurrence.reminder_sent_at.is_(None),
            DutyOccurrence.is_done.is_(False),
            DutyOccurrence.due_date <= on_date,
        )
    )
    occurrences = list(result.scalars())
    if not occurrences:
        return

    payloads = []
    for occurrence in occurrences:
        duty = duty_by_id.get(occurrence.duty_id)
        title = f"Reminder: {duty.title if duty else 'a duty'}"
        url = f"/duties/{occurrence.duty_id}"
        session.add(
            Notification(
                user_id=occurrence.assigned_user_id,
                kind="duty_reminder",
                title=title,
                body=f"Due {occurrence.due_date.isoformat()}",
                url=url,
            )
        )
        occurrence.reminder_sent_at = now
        payloads.append((occurrence.assigned_user_id, title, url))

    await session.commit()

    for user_id, title, url in payloads:
        await send_push_to_user(session, user_id, {"title": title, "url": url})


async def send_task_reminders(session: AsyncSession) -> None:
    on_date = today()
    now = datetime.now(timezone.utc)

    result = await session.execute(
        select(Task)
        .options(selectinload(Task.assignees))
        .where(
            Task.reminder_sent_at.is_(None),
            Task.is_done.is_(False),
            Task.due_date.is_not(None),
            Task.due_date <= on_date,
        )
    )
    tasks = list(result.scalars().unique())
    if not tasks:
        return

    payloads = []
    for task in tasks:
        title = f"Reminder: {task.title}"
        for assignee in task.assignees:
            session.add(
                Notification(
                    user_id=assignee.user_id,
                    kind="task_reminder",
                    title=title,
                    body=f"Due {task.due_date.isoformat()}",
                    url="/tasks",
                )
            )
            payloads.append((assignee.user_id, title))
        task.reminder_sent_at = now

    await session.commit()

    for user_id, title in payloads:
        await send_push_to_user(session, user_id, {"title": title, "url": "/tasks"})


async def run_all_reminders(session: AsyncSession) -> None:
    await send_event_reminders(session)
    await send_duty_reminders(session)
    await send_task_reminders(session)
