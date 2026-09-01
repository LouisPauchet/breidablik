"""Applying an absence's opt-in auto-reassign flag to already-materialized DutyOccurrence
rows: hands them off to the next available person in that duty's rotation instead of leaving
them flagged for a human to swap manually (see app/services/absences.py:is_user_away).
Occurrences created *after* the absence exists are handled at materialization time instead
(see app/services/occurrences.py) — this module only needs to catch up whatever was already
snapshotted before the absence (or its auto_reassign flag) was set.
"""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.absence import Absence
from app.models.duty import Duty, DutyAssignee, DutyOccurrence, DutyTeamMember
from app.services.absences import is_user_away, load_active_absences_by_user
from app.services.rotation import sorted_assignees, sorted_team_members


def pick_reassignment(
    candidates: list[uuid.UUID],
    absent_user_id: uuid.UUID,
    away_user_ids_on_date: set[uuid.UUID],
) -> uuid.UUID | None:
    """The next person after `absent_user_id` in rotation order who isn't also away that day.
    Returns None if there's nobody else to hand it to (single-person rotation, or everyone
    else is also away) — the occurrence is left as-is for a human to sort out.
    """
    if absent_user_id not in candidates or len(candidates) <= 1:
        return None
    start = candidates.index(absent_user_id)
    for offset in range(1, len(candidates) + 1):
        candidate = candidates[(start + offset) % len(candidates)]
        if candidate != absent_user_id and candidate not in away_user_ids_on_date:
            return candidate
    return None


async def _affected_duties(session: AsyncSession, user_id: uuid.UUID) -> list[Duty]:
    direct_result = await session.execute(
        select(Duty)
        .join(DutyAssignee, DutyAssignee.duty_id == Duty.id)
        .where(DutyAssignee.user_id == user_id, Duty.is_active.is_(True))
    )
    duties = list(direct_result.scalars().unique())

    team_ids_result = await session.execute(
        select(DutyTeamMember.team_id).where(DutyTeamMember.user_id == user_id)
    )
    team_ids = [row[0] for row in team_ids_result.all()]
    if team_ids:
        team_duties_result = await session.execute(
            select(Duty).where(Duty.team_id.in_(team_ids), Duty.is_active.is_(True))
        )
        duties += list(team_duties_result.scalars().unique())
    return duties


async def ordered_candidates_for_duty(session: AsyncSession, duty: Duty) -> list[uuid.UUID]:
    if duty.team_id is not None:
        result = await session.execute(
            select(DutyTeamMember).where(DutyTeamMember.team_id == duty.team_id)
        )
        return [m.user_id for m in sorted_team_members(list(result.scalars()))]
    result = await session.execute(select(DutyAssignee).where(DutyAssignee.duty_id == duty.id))
    return [a.user_id for a in sorted_assignees(list(result.scalars()))]


async def reassign_occurrences_for_absence(session: AsyncSession, absence: Absence) -> None:
    """Idempotent: only touches occurrences still assigned to the absent user, so calling
    this more than once (e.g. once here at absence-creation time, once implicitly via
    materialization for occurrences created later) never clobbers an unrelated swap someone
    already made by hand.
    """
    if not absence.auto_reassign:
        return

    duties = await _affected_duties(session, absence.user_id)
    if not duties:
        return

    changed = False
    for duty in duties:
        candidates = await ordered_candidates_for_duty(session, duty)
        if absence.user_id not in candidates:
            continue

        occ_result = await session.execute(
            select(DutyOccurrence).where(
                DutyOccurrence.duty_id == duty.id,
                DutyOccurrence.assigned_user_id == absence.user_id,
                DutyOccurrence.due_date >= absence.start_date,
                DutyOccurrence.due_date <= absence.end_date,
            )
        )
        occurrences = list(occ_result.scalars())
        if not occurrences:
            continue

        absences_by_user = await load_active_absences_by_user(session, candidates)
        for occurrence in occurrences:
            away_today = {
                c for c in candidates if is_user_away(absences_by_user, c, occurrence.due_date)
            }
            replacement = pick_reassignment(candidates, absence.user_id, away_today)
            if replacement is None:
                continue
            occurrence.assigned_user_id = replacement
            occurrence.is_manual_override = True
            changed = True

    if changed:
        await session.commit()
