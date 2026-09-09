"""Contest duties: open, unassigned, unscheduled chores anyone logs whenever they do them
(see app/models/contests.py). The monthly "best performer" award is computed by
app/services/awards.py's finalize step, not here — this module is just creation, logging,
and the current-month tally used to render the leaderboard.
"""

import uuid
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.contests import ContestDuty, ContestLogEntry
from app.models.user import User
from app.timeutils import today


class TooSoonError(Exception):
    """Raised when a contest's household-wide cooldown hasn't elapsed yet."""

    def __init__(self, ready_at: datetime):
        super().__init__("LOG_TOO_SOON")
        self.ready_at = ready_at


def _next_month(d: date) -> date:
    if d.month == 12:
        return date(d.year + 1, 1, 1)
    return date(d.year, d.month + 1, 1)


def current_month_bounds(on_date: date | None = None) -> tuple[date, date]:
    on_date = on_date or today()
    month_start = date(on_date.year, on_date.month, 1)
    month_end = _next_month(month_start) - timedelta(days=1)
    return month_start, month_end


async def create_contest_duty(
    session: AsyncSession,
    *,
    title: str,
    description: str | None,
    icon: str,
    min_interval_minutes: int,
    show_on_home: bool,
    created_by_id: uuid.UUID,
) -> ContestDuty:
    contest = ContestDuty(
        title=title,
        description=description,
        icon=icon,
        min_interval_minutes=min_interval_minutes,
        show_on_home=show_on_home,
        created_by_id=created_by_id,
    )
    session.add(contest)
    await session.commit()
    await session.refresh(contest)
    return contest


async def update_contest_duty(
    session: AsyncSession,
    contest: ContestDuty,
    *,
    title: str | None,
    description: str | None,
    icon: str | None,
    min_interval_minutes: int | None,
    show_on_home: bool | None,
    is_active: bool | None,
) -> ContestDuty:
    if title is not None:
        contest.title = title
    if description is not None:
        contest.description = description
    if icon is not None:
        contest.icon = icon
    if min_interval_minutes is not None:
        contest.min_interval_minutes = min_interval_minutes
    if show_on_home is not None:
        contest.show_on_home = show_on_home
    if is_active is not None:
        contest.is_active = is_active
    await session.commit()
    return contest


def _as_utc(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)


async def next_log_allowed_at(session: AsyncSession, contest: ContestDuty) -> datetime | None:
    """When this contest can next be logged by anyone, or None if it's loggable right now.

    The cooldown is household-wide on purpose (see ContestDuty.min_interval_minutes): the
    chore itself can only genuinely be done once per interval, no matter who does it.
    """
    if contest.min_interval_minutes <= 0:
        return None
    result = await session.execute(
        select(ContestLogEntry.logged_at)
        .where(ContestLogEntry.contest_duty_id == contest.id)
        .order_by(ContestLogEntry.logged_at.desc())
        .limit(1)
    )
    last_logged_at = result.scalar_one_or_none()
    if last_logged_at is None:
        return None
    ready_at = _as_utc(last_logged_at) + timedelta(minutes=contest.min_interval_minutes)
    return ready_at if ready_at > datetime.now(timezone.utc) else None


async def log_completion(session: AsyncSession, contest: ContestDuty, user_id: uuid.UUID) -> ContestLogEntry:
    ready_at = await next_log_allowed_at(session, contest)
    if ready_at is not None:
        raise TooSoonError(ready_at)

    entry = ContestLogEntry(contest_duty_id=contest.id, user_id=user_id)
    session.add(entry)
    await session.commit()
    await session.refresh(entry)
    return entry


async def delete_log_entry(
    session: AsyncSession, contest_duty_id: uuid.UUID, entry_id: uuid.UUID, requesting_user: User
) -> None:
    result = await session.execute(
        select(ContestLogEntry).where(
            ContestLogEntry.id == entry_id, ContestLogEntry.contest_duty_id == contest_duty_id
        )
    )
    entry = result.scalar_one_or_none()
    if entry is None:
        raise LookupError("LOG_ENTRY_NOT_FOUND")
    if entry.user_id != requesting_user.id and not requesting_user.is_superuser:
        raise PermissionError("NOT_YOUR_LOG_ENTRY")
    await session.delete(entry)
    await session.commit()


async def get_my_month_counts(
    session: AsyncSession,
    contest_duty_ids: list[uuid.UUID],
    user_id: uuid.UUID,
    month_start: date,
    month_end: date,
) -> dict[uuid.UUID, int]:
    """Returns {contest_duty_id: count} of the given user's own entries in the (inclusive)
    household-local calendar date range.

    Deliberately only the caller's own count — nobody sees anyone else's running total during
    the month, so the contest doesn't turn into a live scoreboard. The winner is revealed at
    month end by app/services/awards.py's finalize step.

    There's no due_date to filter by in SQL the way DutyOccurrence has (see
    app/services/awards.py:_compute_duty_master) — logged_at is the only signal — so this
    buckets by local date in Python, with the same normalize-naive-as-UTC defensiveness.
    """
    if not contest_duty_ids:
        return {}
    result = await session.execute(
        select(ContestLogEntry).where(
            ContestLogEntry.contest_duty_id.in_(contest_duty_ids), ContestLogEntry.user_id == user_id
        )
    )
    zone = get_settings().zone_info
    counts: dict[uuid.UUID, int] = {}
    for entry in result.scalars():
        local_date = _as_utc(entry.logged_at).astimezone(zone).date()
        if month_start <= local_date <= month_end:
            counts[entry.contest_duty_id] = counts.get(entry.contest_duty_id, 0) + 1
    return counts


async def list_active_contests_for_user(
    session: AsyncSession, user_id: uuid.UUID, *, home_only: bool = False
) -> list[dict]:
    query = select(ContestDuty).where(ContestDuty.is_active.is_(True))
    if home_only:
        query = query.where(ContestDuty.show_on_home.is_(True))
    contests = list((await session.execute(query)).scalars())

    month_start, month_end = current_month_bounds()
    my_counts = await get_my_month_counts(session, [c.id for c in contests], user_id, month_start, month_end)

    return [
        {
            "contest": contest,
            "my_count": my_counts.get(contest.id, 0),
            "next_log_allowed_at": await next_log_allowed_at(session, contest),
        }
        for contest in contests
    ]
