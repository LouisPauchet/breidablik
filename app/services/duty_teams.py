"""Resolves current-period chore-wheel assignments for a DutyTeam — shared by the per-duty
current_period computation (app/routers/duties.py, when a duty is team-attached) and the
team overview endpoint (app/routers/duty_teams.py).
"""

import uuid
from datetime import date, timedelta

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.duty import Duty, DutyOccurrence, DutyOverride, DutyTeam
from app.services.occurrences import DEFAULT_HORIZON_DAYS, ensure_occurrences_materialized
from app.services.rotation import (
    compute_period_index,
    overrides_by_period_index,
    resolve_team_duty_assignee,
    sorted_team_members,
    team_duty_index,
)
from app.timeutils import today


async def load_team_with_relations(session: AsyncSession, team_id: uuid.UUID) -> DutyTeam | None:
    result = await session.execute(
        select(DutyTeam)
        .options(selectinload(DutyTeam.members), selectinload(DutyTeam.duties))
        .where(DutyTeam.id == team_id)
    )
    return result.scalar_one_or_none()


async def resolve_team_duty_current_assignee(
    session: AsyncSession, team: DutyTeam, duty: Duty, on_date: date | None = None
) -> uuid.UUID:
    ordered_members = sorted_team_members(team.members)
    duty_index = team_duty_index(team.duties, duty.id)
    period_index = compute_period_index(team, on_date or today())

    overrides_result = await session.execute(select(DutyOverride).where(DutyOverride.duty_id == duty.id))
    overrides_by_period = overrides_by_period_index(list(overrides_result.scalars()))

    return resolve_team_duty_assignee(ordered_members, duty_index, period_index, overrides_by_period)


async def resolve_all_current_assignments(
    session: AsyncSession, team: DutyTeam
) -> dict[uuid.UUID, uuid.UUID]:
    """duty_id -> assignee_user_id for every duty in the team, for the current period."""
    period_index = compute_period_index(team, today())
    ordered_members = sorted_team_members(team.members)

    assignments: dict[uuid.UUID, uuid.UUID] = {}
    for duty in team.duties:
        duty_index = team_duty_index(team.duties, duty.id)
        overrides_result = await session.execute(
            select(DutyOverride).where(DutyOverride.duty_id == duty.id)
        )
        overrides_by_period = overrides_by_period_index(list(overrides_result.scalars()))
        assignments[duty.id] = resolve_team_duty_assignee(
            ordered_members, duty_index, period_index, overrides_by_period
        )
    return assignments


async def redispatch_team_occurrences(session: AsyncSession, team: DutyTeam) -> None:
    """Called whenever a team's membership changes (add/remove/reorder) so the new roster
    takes effect right away instead of only once the rolling materialization horizon —
    already generated under the old roster — eventually runs past it. Only clears
    occurrences that are still pending and haven't been manually swapped: a completed
    occurrence is history, and a manual swap (e.g. someone covering an absence) reflects a
    deliberate decision that a membership change shouldn't silently undo.
    """
    horizon = today() + timedelta(days=DEFAULT_HORIZON_DAYS)
    for duty in team.duties:
        await session.execute(
            delete(DutyOccurrence).where(
                DutyOccurrence.duty_id == duty.id,
                DutyOccurrence.is_done.is_(False),
                DutyOccurrence.is_manual_override.is_(False),
            )
        )
        await session.flush()
        await ensure_occurrences_materialized(session, duty, horizon)
