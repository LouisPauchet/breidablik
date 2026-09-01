"""Aggregates everything the wall-display dashboard shows into one payload (see
app/routers/dashboard.py) — on-duty-today, a short calendar-style agenda, a recent-activity
feed, and the quote of the day. The dashboard is reached via a single collective-wide secret
link rather than a per-user login (see DashboardConfig), so this intentionally denormalizes
display names/avatars into the response instead of expecting the page to call any of the
normal authenticated endpoints.
"""

import secrets
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.absence import Absence
from app.models.dashboard import DashboardConfig
from app.models.duty import Duty, DutyOccurrence
from app.models.event import Event
from app.models.task import Task
from app.models.user import User
from app.services.duty_status import build_on_duty_today
from app.services.occurrences import ensure_occurrences_materialized
from app.services.quotes import quote_of_the_day
from app.timeutils import today

UPCOMING_HORIZON_DAYS = 10
ACTIVITY_LIMIT = 8


async def get_or_create_dashboard_config(session: AsyncSession) -> DashboardConfig:
    result = await session.execute(select(DashboardConfig).where(DashboardConfig.id == 1))
    config = result.scalar_one_or_none()
    if config is None:
        config = DashboardConfig(id=1)
        session.add(config)
        await session.commit()
        await session.refresh(config)
    return config


async def regenerate_dashboard_token(session: AsyncSession) -> DashboardConfig:
    config = await get_or_create_dashboard_config(session)
    config.token = secrets.token_urlsafe(32)
    await session.commit()
    return config


def _aware_utc(dt: datetime) -> datetime:
    # DateTime columns in this app round-trip as naive on SQLite even when declared
    # timezone=True (see app/auth/device_trust.py for the same fix) and Postgres' plain
    # (non-tz) columns come back naive too, despite always being written as UTC — either
    # way, a naive value here can be safely treated as UTC.
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)


def _at_midnight(on_date: date) -> datetime:
    return datetime.combine(on_date, datetime.min.time(), tzinfo=timezone.utc)


def _next_birthday(birthday: date, on_date: date) -> date:
    candidate = date(on_date.year, birthday.month, birthday.day)
    if candidate < on_date:
        candidate = date(on_date.year + 1, birthday.month, birthday.day)
    return candidate


async def _build_on_duty(session: AsyncSession, on_date: date, members_by_id: dict[object, User]) -> list[dict]:
    entries = await build_on_duty_today(session, on_date)
    out = []
    for entry in entries:
        member = members_by_id.get(entry["assignee_user_id"])
        out.append(
            {
                **entry,
                "assignee_display_name": member.display_name if member else "Someone",
                "assignee_avatar_updated_at": member.avatar_updated_at if member else None,
            }
        )
    return out


async def _build_upcoming(session: AsyncSession, on_date: date, members_by_id: dict[object, User]) -> list[dict]:
    date_horizon = on_date + timedelta(days=UPCOMING_HORIZON_DAYS)
    dt_window_start = datetime.now(timezone.utc)
    dt_window_end = dt_window_start + timedelta(days=UPCOMING_HORIZON_DAYS)

    entries: list[dict] = []

    duties_result = await session.execute(
        select(Duty)
        .options(selectinload(Duty.assignees), selectinload(Duty.overrides))
        .where(Duty.is_active.is_(True))
    )
    duties = duties_result.scalars().unique().all()
    duty_by_id = {d.id: d for d in duties}
    for duty in duties:
        await ensure_occurrences_materialized(session, duty, date_horizon)

    if duty_by_id:
        occ_result = await session.execute(
            select(DutyOccurrence).where(
                DutyOccurrence.duty_id.in_(duty_by_id.keys()),
                DutyOccurrence.due_date >= on_date,
                DutyOccurrence.due_date <= date_horizon,
                DutyOccurrence.is_done.is_(False),
            )
        )
        for occ in occ_result.scalars():
            assignee = members_by_id.get(occ.assigned_user_id)
            entries.append(
                {
                    "key": f"duty-{occ.id}",
                    "kind": "duty",
                    "title": duty_by_id[occ.duty_id].title,
                    "detail": assignee.display_name if assignee else "",
                    "at": _at_midnight(occ.due_date),
                }
            )

    tasks_result = await session.execute(
        select(Task).where(
            Task.is_done.is_(False),
            Task.due_date.is_not(None),
            Task.due_date >= on_date,
            Task.due_date <= date_horizon,
        )
    )
    for task in tasks_result.scalars():
        entries.append(
            {
                "key": f"task-{task.id}",
                "kind": "task",
                "title": task.title,
                "detail": "",
                "at": _at_midnight(task.due_date),
            }
        )

    events_result = await session.execute(
        select(Event)
        .where(Event.start_at >= dt_window_start, Event.start_at <= dt_window_end)
        .order_by(Event.start_at)
    )
    for event in events_result.scalars():
        entries.append(
            {
                "key": f"event-{event.id}",
                "kind": "event",
                "title": event.title,
                "detail": event.location or "",
                "at": _aware_utc(event.start_at),
            }
        )

    absences_result = await session.execute(
        select(Absence).where(Absence.start_date <= date_horizon, Absence.end_date >= on_date)
    )
    for absence in absences_result.scalars():
        member = members_by_id.get(absence.user_id)
        entries.append(
            {
                "key": f"away-{absence.id}",
                "kind": "away",
                "title": f"{member.display_name if member else 'Someone'} away",
                "detail": absence.reason or "",
                "at": _at_midnight(max(absence.start_date, on_date)),
            }
        )

    for member in members_by_id.values():
        if not member.birthday:
            continue
        next_birthday = _next_birthday(member.birthday, on_date)
        if next_birthday > date_horizon:
            continue
        entries.append(
            {
                "key": f"birthday-{member.id}-{next_birthday.isoformat()}",
                "kind": "birthday",
                "title": f"{member.display_name}'s birthday",
                "detail": "",
                "at": _at_midnight(next_birthday),
            }
        )

    entries.sort(key=lambda e: e["at"])
    return entries


async def _build_activity(session: AsyncSession, members_by_id: dict[object, User]) -> list[dict]:
    entries: list[dict] = []

    done_occ_result = await session.execute(
        select(DutyOccurrence, Duty.title)
        .join(Duty, DutyOccurrence.duty_id == Duty.id)
        .where(DutyOccurrence.is_done.is_(True), DutyOccurrence.done_at.is_not(None))
        .order_by(DutyOccurrence.done_at.desc())
        .limit(ACTIVITY_LIMIT)
    )
    for occ, duty_title in done_occ_result.all():
        doer = members_by_id.get(occ.done_by_id)
        entries.append(
            {
                "at": _aware_utc(occ.done_at),
                "text": f'{doer.display_name if doer else "Someone"} completed "{duty_title}"',
            }
        )

    done_task_result = await session.execute(
        select(Task)
        .where(Task.is_done.is_(True), Task.done_at.is_not(None))
        .order_by(Task.done_at.desc())
        .limit(ACTIVITY_LIMIT)
    )
    for task in done_task_result.scalars():
        doer = members_by_id.get(task.done_by_id)
        entries.append(
            {
                "at": _aware_utc(task.done_at),
                "text": f'{doer.display_name if doer else "Someone"} completed "{task.title}"',
            }
        )

    new_event_result = await session.execute(
        select(Event).order_by(Event.created_at.desc()).limit(ACTIVITY_LIMIT)
    )
    for event in new_event_result.scalars():
        creator = members_by_id.get(event.created_by_id)
        entries.append(
            {
                "at": _aware_utc(event.created_at),
                "text": f'{creator.display_name if creator else "Someone"} added "{event.title}" to the calendar',
            }
        )

    entries.sort(key=lambda e: e["at"], reverse=True)
    return entries[:ACTIVITY_LIMIT]


async def build_dashboard_data(session: AsyncSession) -> dict:
    on_date = today()

    members_result = await session.execute(select(User).where(User.is_active.is_(True)))
    members_by_id = {m.id: m for m in members_result.scalars()}

    return {
        "generated_at": datetime.now(timezone.utc),
        "quote": quote_of_the_day(on_date),
        "on_duty_today": await _build_on_duty(session, on_date, members_by_id),
        "upcoming": await _build_upcoming(session, on_date, members_by_id),
        "activity": await _build_activity(session, members_by_id),
    }
