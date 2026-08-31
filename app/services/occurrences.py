"""Lazy materialization of DutyOccurrence rows, invoked whenever a duty's occurrences need
to be visible (duty detail view, combined calendar) rather than by any background job — see
plan doc, Domain model: Duties. Team-attached duties (duty.team_id set) resolve their
assignee via the team's chore-wheel rotation instead of the duty's own assignees/rotation
formula — see app/services/rotation.py.
"""

from collections.abc import Callable
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.duty import Duty, DutyAssignee, DutyOccurrence, DutyOverride, DutyTeam
from app.services.rotation import (
    compute_period_index,
    overrides_by_period_index,
    resolve_assignee_for_period,
    resolve_team_duty_assignee,
    sorted_assignees,
    sorted_team_members,
    team_duty_index,
)

DEFAULT_HORIZON_DAYS = 56  # 8 weeks


async def ensure_occurrences_materialized(session: AsyncSession, duty: Duty, horizon: date) -> None:
    if duty.team_id is not None:
        await _ensure_team_duty_occurrences_materialized(session, duty, horizon)
        return

    assignees_result = await session.execute(select(DutyAssignee).where(DutyAssignee.duty_id == duty.id))
    ordered_assignees = sorted_assignees(list(assignees_result.scalars()))
    if not ordered_assignees:
        return

    overrides_result = await session.execute(select(DutyOverride).where(DutyOverride.duty_id == duty.id))
    overrides_by_period = overrides_by_period_index(list(overrides_result.scalars()))

    await _materialize(
        session,
        duty,
        horizon,
        period_index_fn=lambda due: compute_period_index(duty, due),
        resolve_fn=lambda period_index: resolve_assignee_for_period(
            ordered_assignees, overrides_by_period, period_index
        ),
    )


async def _ensure_team_duty_occurrences_materialized(session: AsyncSession, duty: Duty, horizon: date) -> None:
    team_result = await session.execute(
        select(DutyTeam)
        .options(selectinload(DutyTeam.members), selectinload(DutyTeam.duties))
        .where(DutyTeam.id == duty.team_id)
    )
    team = team_result.scalar_one_or_none()
    if team is None:
        return

    ordered_members = sorted_team_members(team.members)
    if not ordered_members:
        return
    duty_index = team_duty_index(team.duties, duty.id)

    overrides_result = await session.execute(select(DutyOverride).where(DutyOverride.duty_id == duty.id))
    overrides_by_period = overrides_by_period_index(list(overrides_result.scalars()))

    await _materialize(
        session,
        duty,
        horizon,
        period_index_fn=lambda due: compute_period_index(team, due),
        resolve_fn=lambda period_index: resolve_team_duty_assignee(
            ordered_members, duty_index, period_index, overrides_by_period
        ),
    )


async def _materialize(
    session: AsyncSession,
    duty: Duty,
    horizon: date,
    period_index_fn: Callable[[date], int],
    resolve_fn: Callable[[int], object],
) -> None:
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
        period_index = period_index_fn(due)
        assignee_id = resolve_fn(period_index)
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
