"""Who's on duty for what, right now — shared by the authenticated /api/duties/on-duty-today
endpoint, the public dashboard (app/services/dashboard.py), and the shopping-list notification
(app/services/notifications.py), all of which need exactly the same team-vs-individual
rotation resolution. This used to be duplicated per call site, and the shopping notification's
copy was never updated to handle team-attached duties — see resolve_current_assignee below.
"""

from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.duty import Duty
from app.services.duty_teams import load_team_with_relations, resolve_team_duty_current_assignee
from app.services.rotation import (
    compute_period_index,
    overrides_by_period_index,
    resolve_assignee_for_period,
    sorted_assignees,
)


async def resolve_current_assignee(session: AsyncSession, duty: Duty, on_date: date) -> object | None:
    """Who's currently responsible for `duty`, or None if it can't be resolved (no members/
    assignees configured yet). `duty.assignees`/`duty.overrides` must already be loaded for
    the individual-duty branch; the team branch loads what it needs itself.
    """
    if duty.team_id is not None:
        team = await load_team_with_relations(session, duty.team_id)
        if team is None or not team.members:
            return None
        return await resolve_team_duty_current_assignee(session, team, duty, on_date)

    ordered = sorted_assignees(duty.assignees)
    if not ordered:
        return None
    period_index = compute_period_index(duty, on_date)
    overrides_by_period = overrides_by_period_index(duty.overrides)
    return resolve_assignee_for_period(ordered, overrides_by_period, period_index)


async def build_on_duty_today(session: AsyncSession, on_date: date) -> list[dict]:
    result = await session.execute(
        select(Duty)
        .options(selectinload(Duty.assignees), selectinload(Duty.overrides))
        .where(Duty.is_active.is_(True))
    )
    duties = result.scalars().unique().all()

    out = []
    for duty in duties:
        assignee_id = await resolve_current_assignee(session, duty, on_date)
        if assignee_id is None:
            continue
        out.append({"duty_id": duty.id, "duty_title": duty.title, "assignee_user_id": assignee_id})
    return out
