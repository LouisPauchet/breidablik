"""Contest duties: open, unassigned, unscheduled chores anyone logs whenever they do them
(see app/models/contests.py). The monthly "best performer" award is computed by
app/services/awards.py's finalize step, not here — this module is just creation, logging,
and the current-month tally used to render the leaderboard.
"""

import uuid
from collections import defaultdict
from datetime import date, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.contests import ContestDuty, ContestLogEntry
from app.models.user import User
from app.timeutils import today


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
    session: AsyncSession, *, title: str, description: str | None, icon: str, created_by_id: uuid.UUID
) -> ContestDuty:
    contest = ContestDuty(title=title, description=description, icon=icon, created_by_id=created_by_id)
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
    is_active: bool | None,
) -> ContestDuty:
    if title is not None:
        contest.title = title
    if description is not None:
        contest.description = description
    if icon is not None:
        contest.icon = icon
    if is_active is not None:
        contest.is_active = is_active
    await session.commit()
    return contest


async def log_completion(session: AsyncSession, contest_duty_id: uuid.UUID, user_id: uuid.UUID) -> ContestLogEntry:
    entry = ContestLogEntry(contest_duty_id=contest_duty_id, user_id=user_id)
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


async def get_month_tally(
    session: AsyncSession, contest_duty_ids: list[uuid.UUID], month_start: date, month_end: date
) -> dict[uuid.UUID, dict[uuid.UUID, int]]:
    """Returns {contest_duty_id: {user_id: count}} for entries logged within the given
    (inclusive) household-local calendar date range. There's no due_date to filter by in SQL
    the way DutyOccurrence has (see app/services/awards.py:_compute_duty_master) — logged_at
    is the only signal — so this fetches the (household-scale, small) full set per contest
    and buckets by local date in Python, same normalize-naive-as-UTC defensiveness as
    _compute_duty_master.
    """
    if not contest_duty_ids:
        return {}
    result = await session.execute(
        select(ContestLogEntry).where(ContestLogEntry.contest_duty_id.in_(contest_duty_ids))
    )
    zone = get_settings().zone_info
    tally: dict[uuid.UUID, dict[uuid.UUID, int]] = defaultdict(lambda: defaultdict(int))
    for entry in result.scalars():
        logged_at = entry.logged_at
        if logged_at.tzinfo is None:
            logged_at = logged_at.replace(tzinfo=timezone.utc)
        local_date = logged_at.astimezone(zone).date()
        if month_start <= local_date <= month_end:
            tally[entry.contest_duty_id][entry.user_id] += 1
    return {k: dict(v) for k, v in tally.items()}


async def list_active_contests_with_tally(session: AsyncSession) -> list[dict]:
    result = await session.execute(select(ContestDuty).where(ContestDuty.is_active.is_(True)))
    contests = list(result.scalars())
    month_start, month_end = current_month_bounds()
    tally_by_contest = await get_month_tally(session, [c.id for c in contests], month_start, month_end)

    return [
        {
            "contest": contest,
            "tally": [
                {"user_id": user_id, "count": count}
                for user_id, count in sorted(
                    tally_by_contest.get(contest.id, {}).items(), key=lambda kv: kv[1], reverse=True
                )
            ],
        }
        for contest in contests
    ]
