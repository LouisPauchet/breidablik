"""Rotation resolution for a Duty's two independent cadences: how often the chore needs
doing (task_interval_days) and how often the responsible person changes
(rotation_interval_days) — e.g. bathroom cleaned weekly, responsibility rotates every two
weeks. Pure functions, no I/O, so the edge cases (pre-start dates, single assignee,
reordering) are easy to unit test directly.
"""

import uuid
from datetime import date, timedelta

from app.models.duty import Duty, DutyAssignee, DutyOverride


def compute_period_index(duty: Duty, on_date: date) -> int:
    days_elapsed = (on_date - duty.start_date).days
    # Python's floor division on a negative dividend still gives a well-defined, monotonic
    # period index for dates before start_date (e.g. -1 // 7 == -1, not 0).
    return days_elapsed // duty.rotation_interval_days


def period_bounds(duty: Duty, period_index: int) -> tuple[date, date]:
    start = duty.start_date + timedelta(days=period_index * duty.rotation_interval_days)
    end = start + timedelta(days=duty.rotation_interval_days - 1)
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
