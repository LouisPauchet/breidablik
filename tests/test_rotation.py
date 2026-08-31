import uuid
from datetime import date

from app.models.duty import Duty, DutyAssignee, DutyOverride
from app.services.rotation import (
    compute_period_index,
    compute_rotation_assignee,
    overrides_by_period_index,
    period_bounds,
    resolve_assignee_for_period,
)

ALICE = uuid.uuid4()
BOB = uuid.uuid4()
CARL = uuid.uuid4()


def make_duty(start_date: date, task_interval_days: int = 7, rotation_interval_days: int = 14) -> Duty:
    return Duty(
        id=uuid.uuid4(),
        title="Bathroom",
        start_date=start_date,
        task_interval_days=task_interval_days,
        rotation_interval_days=rotation_interval_days,
        created_by_id=uuid.uuid4(),
    )


def make_assignees(duty_id, user_ids) -> list[DutyAssignee]:
    return [
        DutyAssignee(duty_id=duty_id, user_id=uid, order_index=i) for i, uid in enumerate(user_ids)
    ]


def test_period_index_at_start_date_is_zero():
    duty = make_duty(date(2026, 1, 1))
    assert compute_period_index(duty, date(2026, 1, 1)) == 0


def test_period_index_advances_by_rotation_interval():
    duty = make_duty(date(2026, 1, 1), rotation_interval_days=14)
    assert compute_period_index(duty, date(2026, 1, 13)) == 0
    assert compute_period_index(duty, date(2026, 1, 14)) == 0
    assert compute_period_index(duty, date(2026, 1, 15)) == 1
    assert compute_period_index(duty, date(2026, 1, 28)) == 1
    assert compute_period_index(duty, date(2026, 1, 29)) == 2


def test_period_index_before_start_date_is_well_defined():
    duty = make_duty(date(2026, 1, 15), rotation_interval_days=7)
    # One day before start_date falls into the period immediately preceding period 0.
    assert compute_period_index(duty, date(2026, 1, 14)) == -1
    assert compute_period_index(duty, date(2026, 1, 8)) == -1
    assert compute_period_index(duty, date(2026, 1, 7)) == -2


def test_rotation_assignee_cycles_through_ordered_assignees():
    assignees = make_assignees(uuid.uuid4(), [ALICE, BOB, CARL])
    assert compute_rotation_assignee(assignees, 0) == ALICE
    assert compute_rotation_assignee(assignees, 1) == BOB
    assert compute_rotation_assignee(assignees, 2) == CARL
    assert compute_rotation_assignee(assignees, 3) == ALICE


def test_rotation_assignee_negative_period_index_does_not_raise():
    assignees = make_assignees(uuid.uuid4(), [ALICE, BOB, CARL])
    # -1 % 3 == 2 in Python, a well-defined index rather than an IndexError.
    assert compute_rotation_assignee(assignees, -1) == CARL


def test_rotation_assignee_single_assignee_always_same():
    assignees = make_assignees(uuid.uuid4(), [ALICE])
    for period_index in range(-3, 5):
        assert compute_rotation_assignee(assignees, period_index) == ALICE


def test_rotation_assignee_no_assignees_raises():
    try:
        compute_rotation_assignee([], 0)
        assert False, "expected ValueError"
    except ValueError:
        pass


def test_override_takes_precedence_over_formula():
    assignees = make_assignees(uuid.uuid4(), [ALICE, BOB])
    overrides = {1: CARL}
    assert resolve_assignee_for_period(assignees, overrides, 0) == ALICE
    assert resolve_assignee_for_period(assignees, overrides, 1) == CARL
    assert resolve_assignee_for_period(assignees, overrides, 2) == ALICE


def test_overrides_by_period_index_builds_lookup():
    duty_id = uuid.uuid4()
    overrides = [
        DutyOverride(duty_id=duty_id, period_index=0, assignee_user_id=ALICE, created_by_id=BOB),
        DutyOverride(duty_id=duty_id, period_index=3, assignee_user_id=BOB, created_by_id=ALICE),
    ]
    lookup = overrides_by_period_index(overrides)
    assert lookup == {0: ALICE, 3: BOB}


def test_period_bounds_span_rotation_interval():
    duty = make_duty(date(2026, 1, 1), rotation_interval_days=14)
    start, end = period_bounds(duty, 0)
    assert start == date(2026, 1, 1)
    assert end == date(2026, 1, 14)

    start, end = period_bounds(duty, 1)
    assert start == date(2026, 1, 15)
    assert end == date(2026, 1, 28)


def test_rotation_interval_not_a_multiple_of_task_interval_still_resolves():
    # Rotation every 10 days, task due every 7 days — periods don't align cleanly with
    # occurrences, which is fine: each due_date just resolves its own period independently.
    duty = make_duty(date(2026, 1, 1), task_interval_days=7, rotation_interval_days=10)
    assignees = make_assignees(uuid.uuid4(), [ALICE, BOB])

    due_dates = [date(2026, 1, 1), date(2026, 1, 8), date(2026, 1, 15), date(2026, 1, 22)]
    periods = [compute_period_index(duty, d) for d in due_dates]
    assert periods == [0, 0, 1, 2]
    resolved = [compute_rotation_assignee(assignees, p) for p in periods]
    assert resolved == [ALICE, ALICE, BOB, ALICE]
