"""Builds a per-user iCalendar feed for external subscription (Google/Apple/Outlook), per
the plan's Calendar subscription flow: the user's own duty occurrences and tasks, every
collective event, and other members' absences (marked transparent — informational, not
blocking time). Each VEVENT's UID is derived from its source row so a calendar app's
periodic refetch updates existing entries instead of duplicating them.
"""

from datetime import datetime, timedelta, timezone

from icalendar import Calendar
from icalendar import Event as VEvent
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.absence import Absence
from app.models.duty import Duty, DutyOccurrence
from app.models.event import Event
from app.models.task import Task, TaskAssignee
from app.models.user import User
from app.services.occurrences import DEFAULT_HORIZON_DAYS, ensure_occurrences_materialized
from app.timeutils import today

FEED_PAST_DAYS = 7
FEED_FUTURE_DAYS = DEFAULT_HORIZON_DAYS


async def build_ics_for_user(session: AsyncSession, user: User) -> bytes:
    cal = Calendar()
    cal.add("prodid", "-//Breidablik//breidablik//EN")
    cal.add("version", "2.0")
    cal.add("x-wr-calname", f"Breidablik - {user.display_name}")

    on_date = today()
    date_window_start = on_date - timedelta(days=FEED_PAST_DAYS)
    date_window_end = on_date + timedelta(days=FEED_FUTURE_DAYS)
    now = datetime.now(timezone.utc)
    dt_window_start = now - timedelta(days=FEED_PAST_DAYS)
    dt_window_end = now + timedelta(days=FEED_FUTURE_DAYS)

    duties_result = await session.execute(
        select(Duty)
        .options(selectinload(Duty.assignees), selectinload(Duty.overrides))
        .where(Duty.is_active.is_(True))
    )
    duties = list(duties_result.scalars().unique())
    duty_by_id = {d.id: d for d in duties}
    for duty in duties:
        await ensure_occurrences_materialized(session, duty, date_window_end)

    occ_result = await session.execute(
        select(DutyOccurrence).where(
            DutyOccurrence.assigned_user_id == user.id,
            DutyOccurrence.due_date >= date_window_start,
            DutyOccurrence.due_date <= date_window_end,
        )
    )
    for occurrence in occ_result.scalars():
        duty = duty_by_id.get(occurrence.duty_id)
        vevent = VEvent()
        vevent.add("uid", f"duty-occurrence-{occurrence.id}@breidablik")
        vevent.add("summary", duty.title if duty else "Duty")
        vevent.add("dtstart", occurrence.due_date)
        vevent.add("dtend", occurrence.due_date + timedelta(days=1))
        vevent.add("dtstamp", now)
        cal.add_component(vevent)

    tasks_result = await session.execute(
        select(Task)
        .join(TaskAssignee, TaskAssignee.task_id == Task.id)
        .where(
            TaskAssignee.user_id == user.id,
            Task.due_date.is_not(None),
            Task.due_date >= date_window_start,
            Task.due_date <= date_window_end,
        )
    )
    for task in tasks_result.scalars().unique():
        vevent = VEvent()
        vevent.add("uid", f"task-{task.id}@breidablik")
        vevent.add("summary", task.title)
        vevent.add("dtstart", task.due_date)
        vevent.add("dtend", task.due_date + timedelta(days=1))
        vevent.add("dtstamp", now)
        cal.add_component(vevent)

    events_result = await session.execute(
        select(Event).where(Event.start_at >= dt_window_start, Event.start_at <= dt_window_end)
    )
    for event in events_result.scalars():
        vevent = VEvent()
        vevent.add("uid", f"event-{event.id}@breidablik")
        vevent.add("summary", event.title)
        vevent.add("dtstart", event.start_at)
        vevent.add("dtend", event.end_at or (event.start_at + timedelta(hours=2)))
        if event.location:
            vevent.add("location", event.location)
        if event.description:
            vevent.add("description", event.description)
        vevent.add("dtstamp", now)
        cal.add_component(vevent)

    absences_result = await session.execute(
        select(Absence).where(Absence.end_date >= date_window_start, Absence.start_date <= date_window_end)
    )
    absences = list(absences_result.scalars())
    if absences:
        members_result = await session.execute(select(User))
        display_name_by_id = {m.id: m.display_name for m in members_result.scalars()}
        for absence in absences:
            vevent = VEvent()
            vevent.add("uid", f"absence-{absence.id}@breidablik")
            name = display_name_by_id.get(absence.user_id, "Someone")
            summary = f"{name} away"
            if absence.reason:
                summary += f" ({absence.reason})"
            vevent.add("summary", summary)
            vevent.add("dtstart", absence.start_date)
            vevent.add("dtend", absence.end_date + timedelta(days=1))
            vevent.add("transp", "TRANSPARENT")
            vevent.add("dtstamp", now)
            cal.add_component(vevent)

    return cal.to_ical()
