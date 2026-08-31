"""Rotation resolution for a Duty's two independent cadences: how often the chore needs
doing (task_interval_days) and how often the responsible person changes. The latter is
either per-duty (rotation_interval_days + assignees, functions in the first half of this
file) or inherited from a DutyTeam's chore-wheel (resolve_team_duty_assignee, second half) —
never both. Pure functions, no I/O, so the edge cases (pre-start dates, single assignee,
reordering) are easy to unit test directly.
"""

import uuid
from datetime import date, timedelta

from app.models.duty import Duty, DutyAssignee, DutyOverride, DutyTeam, DutyTeamMember


def compute_period_index(duty_or_team: Duty | DutyTeam, on_date: date) -> int:
    days_elapsed = (on_date - duty_or_team.start_date).days
    # Python's floor division on a negative dividend still gives a well-defined, monotonic
    # period index for dates before start_date (e.g. -1 // 7 == -1, not 0).
    return days_elapsed // duty_or_team.rotation_interval_days


def period_bounds(duty_or_team: Duty | DutyTeam, period_index: int) -> tuple[date, date]:
    interval = duty_or_team.rotation_interval_days
    start = duty_or_team.start_date + timedelta(days=period_index * interval)
    end = start + timedelta(days=interval - 1)
    return start, end


def compute_rotation_assignee(ordered_assignees: list[DutyAssignee], period_index: int) -> uuid.UUID:
    if not ordered_assignees:
        raise ValueError("Duty has no assignees")
    # Python's modulo on a negative period_index still returns a valid non-negative index
    # when the divisor is positive, so pre-start periods resolve without an IndexError.
    return ordered_assignees[period_index % len(ordered_assignees)].user_id


def overrides_by_period_index(overrides: list[DutyOverride]) -> dict[int, uuid.UUID]:
    return {o.period_index: o.assignee_user_id for o in overrides}


def resolve_assignee_for_period(
    ordered_assignees: list[DutyAssignee],
    overrides_by_period: dict[int, uuid.UUID],
    period_index: int,
) -> uuid.UUID:
    if period_index in overrides_by_period:
        return overrides_by_period[period_index]
    return compute_rotation_assignee(ordered_assignees, period_index)


def sorted_assignees(assignees: list[DutyAssignee]) -> list[DutyAssignee]:
    return sorted(assignees, key=lambda a: a.order_index)


def sorted_team_members(members: list[DutyTeamMember]) -> list[DutyTeamMember]:
    return sorted(members, key=lambda m: m.order_index)


def team_duty_index(team_duties_sorted: list[Duty], duty_id: uuid.UUID) -> int:
    """A duty's stable position among its team's duties (sorted by creation order) — offsetting
    the rotation formula by this is what fans duties out across members within the same
    period instead of every duty following the same single assignee.
    """
    for index, duty in enumerate(team_duties_sorted):
        if duty.id == duty_id:
            return index
    raise ValueError("duty not found in its own team's duty list")


def resolve_team_duty_assignee(
    ordered_members: list[DutyTeamMember],
    duty_index: int,
    team_period_index: int,
    overrides_by_period: dict[int, uuid.UUID],
) -> uuid.UUID:
    """Chore-wheel distribution: each team period, every duty attached to the team goes to a
    different member, rotating again next period. team_period_index is the team's own
    period index (see compute_period_index(team, ...)) — DutyOverride.period_index for a
    team-attached duty is keyed against this, not any per-duty index, so a swap means the
    same thing regardless of which duty it's recorded against.
    """
    if team_period_index in overrides_by_period:
        return overrides_by_period[team_period_index]
    if not ordered_members:
        raise ValueError("Duty team has no members")
    return ordered_members[(team_period_index + duty_index) % len(ordered_members)].user_id
