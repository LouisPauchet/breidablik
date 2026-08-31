"""Lazy materialization of DutyOccurrence rows, invoked whenever a duty's occurrences need
to be visible (duty detail view, combined calendar) rather than by any background job — see
plan doc, Domain model: Duties.
"""

from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.duty import Duty, DutyAssignee, DutyOccurrence, DutyOverride
from app.services.rotation import (
    compute_period_index,
    overrides_by_period_index,
    resolve_assignee_for_period,
    sorted_assignees,
)

DEFAULT_HORIZON_DAYS = 56  # 8 weeks


async def ensure_occurrences_materialized(session: AsyncSession, duty: Duty, horizon: date) -> None:
    assignees_result = await session.execute(
        select(DutyAssignee).where(DutyAssignee.duty_id == duty.id)
    )
    ordered_assignees = sorted_assignees(list(assignees_result.scalars()))
    if not ordered_assignees:
        return

    overrides_result = await session.execute(select(DutyOverride).where(DutyOverride.duty_id == duty.id))
    overrides_by_period = overrides_by_period_index(list(overrides_result.scalars()))

    latest_result = await session.execute(
        select(DutyOccurrence.due_date)
        .where(DutyOccurrence.duty_id == duty.id)
        .order_by(DutyOccurrence.due_date.desc())
        .limit(1)
    )
    latest_due_date = latest_result.scalar_one_or_none()
    next_due = latest_due_date + timedelta(days=duty.task_interval_days) if latest_due_date else duty.start_date

    rows: list[DutyOccurrence] = []
    due = next_due
    while due <= horizon:
        period_index = compute_period_index(duty, due)
        assignee_id = resolve_assignee_for_period(ordered_assignees, overrides_by_period, period_index)
        rows.append(
            DutyOccurrence(
                duty_id=duty.id,
                due_date=due,
                period_index=period_index,
                assigned_user_id=assignee_id,
            )
        )
        due += timedelta(days=duty.task_interval_days)

    if not rows:
        return

    session.add_all(rows)
    try:
        await session.commit()
    except IntegrityError:
        # Another concurrent request (e.g. two members opening the duties page at once)
        # already materialized some/all of these due_dates. Discard this batch — whatever
        # is genuinely still missing gets regenerated correctly next time this runs, since
        # next_due is always recomputed from the current max due_date.
        await session.rollback()
