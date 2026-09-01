"""Who's on duty for what, right now — shared by the authenticated /api/duties/on-duty-today
endpoint and the public dashboard (app/services/dashboard.py), which both need exactly the
same team-vs-individual rotation resolution.
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


async def build_on_duty_today(session: AsyncSession, on_date: date) -> list[dict]:
    result = await session.execute(
        select(Duty)
        .options(selectinload(Duty.assignees), selectinload(Duty.overrides))
        .where(Duty.is_active.is_(True))
    )
    duties = result.scalars().unique().all()

    out = []
    for duty in duties:
        if duty.team_id is not None:
            team = await load_team_with_relations(session, duty.team_id)
            if team is None or not team.members:
                continue
            assignee_id = await resolve_team_duty_current_assignee(session, team, duty, on_date)
        else:
            ordered = sorted_assignees(duty.assignees)
            if not ordered:
                continue
            period_index = compute_period_index(duty, on_date)
            overrides_by_period = overrides_by_period_index(duty.overrides)
            assignee_id = resolve_assignee_for_period(ordered, overrides_by_period, period_index)
        out.append({"duty_id": duty.id, "duty_title": duty.title, "assignee_user_id": assignee_id})
    return out
