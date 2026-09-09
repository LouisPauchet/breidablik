import uuid
from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

import app.services.push as push_module
from app.models.awards import AwardCycle, AwardCyclePhase
from app.models.contests import ContestAwardResult, ContestDuty, ContestLogEntry
from app.models.user import User
from app.services.awards import _compute_contest_winner, run_award_cycle_tick
from app.services.contests import (
    TooSoonError,
    current_month_bounds,
    get_my_month_counts,
    list_active_contests_for_user,
    log_completion,
    next_log_allowed_at,
)

ALICE = uuid.uuid4()
BOB = uuid.uuid4()

CYCLE_MONTH = date(2026, 3, 1)  # same fixed month used in tests/test_awards.py


def _session(test_engine):
    return async_sessionmaker(test_engine, expire_on_commit=False)()


async def _seed_users(session, ids_and_names):
    for user_id, name in ids_and_names:
        session.add(
            User(
                id=user_id,
                email=f"{name.lower()}@example.com",
                hashed_password="x",
                display_name=name,
                is_active=True,
                is_superuser=False,
                is_verified=True,
            )
        )
    await session.commit()


async def _disable_real_push(monkeypatch):
    fake_settings = SimpleNamespace(vapid_private_key="", vapid_claim_email="mailto:test@example.com")
    monkeypatch.setattr(push_module, "get_settings", lambda: fake_settings)


def _at(day: int, hour: int = 12) -> datetime:
    return datetime(CYCLE_MONTH.year, CYCLE_MONTH.month, day, hour, tzinfo=timezone.utc)


async def test_get_my_month_counts_only_counts_my_own_entries(test_engine):
    async with _session(test_engine) as session:
        await _seed_users(session, [(ALICE, "Alice"), (BOB, "Bob")])
        contest = ContestDuty(title="Dishwasher", icon="🍽️", created_by_id=ALICE)
        session.add(contest)
        await session.flush()
        session.add_all(
            [
                ContestLogEntry(contest_duty_id=contest.id, user_id=ALICE, logged_at=_at(5)),
                ContestLogEntry(contest_duty_id=contest.id, user_id=ALICE, logged_at=_at(10)),
                ContestLogEntry(contest_duty_id=contest.id, user_id=BOB, logged_at=_at(6)),
                # Outside the month — must not be counted.
                ContestLogEntry(contest_duty_id=contest.id, user_id=BOB, logged_at=_at(5) - timedelta(days=40)),
            ]
        )
        await session.commit()

        month_start, month_end = current_month_bounds(CYCLE_MONTH)
        assert await get_my_month_counts(session, [contest.id], ALICE, month_start, month_end) == {
            contest.id: 2
        }
        # Bob's own view never includes Alice's two entries.
        assert await get_my_month_counts(session, [contest.id], BOB, month_start, month_end) == {
            contest.id: 1
        }


async def test_list_active_contests_for_user_exposes_only_own_count(test_engine):
    async with _session(test_engine) as session:
        await _seed_users(session, [(ALICE, "Alice"), (BOB, "Bob")])
        contest = ContestDuty(title="Dishwasher", icon="🍽️", created_by_id=ALICE)
        session.add(contest)
        await session.flush()
        session.add_all(
            [
                ContestLogEntry(contest_duty_id=contest.id, user_id=ALICE),
                ContestLogEntry(contest_duty_id=contest.id, user_id=ALICE),
                ContestLogEntry(contest_duty_id=contest.id, user_id=BOB),
            ]
        )
        await session.commit()

        alice_view = await list_active_contests_for_user(session, ALICE)
        bob_view = await list_active_contests_for_user(session, BOB)
        assert alice_view[0]["my_count"] == 2
        assert bob_view[0]["my_count"] == 1
        # No key anywhere in the payload carries another member's tally.
        assert set(alice_view[0]) == {"contest", "my_count", "next_log_allowed_at"}


async def test_home_only_filter(test_engine):
    async with _session(test_engine) as session:
        await _seed_users(session, [(ALICE, "Alice")])
        on_home = ContestDuty(title="Dishwasher", icon="🍽️", created_by_id=ALICE, show_on_home=True)
        off_home = ContestDuty(title="Recycling", icon="♻️", created_by_id=ALICE, show_on_home=False)
        session.add_all([on_home, off_home])
        await session.commit()

        assert len(await list_active_contests_for_user(session, ALICE)) == 2
        home_view = await list_active_contests_for_user(session, ALICE, home_only=True)
        assert [e["contest"].title for e in home_view] == ["Dishwasher"]


async def test_cooldown_blocks_second_log_household_wide(test_engine):
    async with _session(test_engine) as session:
        await _seed_users(session, [(ALICE, "Alice"), (BOB, "Bob")])
        contest = ContestDuty(
            title="Dishwasher", icon="🍽️", created_by_id=ALICE, min_interval_minutes=240
        )
        session.add(contest)
        await session.commit()

        await log_completion(session, contest, ALICE)

        # Alice can't log again...
        try:
            await log_completion(session, contest, ALICE)
            raise AssertionError("expected TooSoonError")
        except TooSoonError as exc:
            assert exc.ready_at > datetime.now(timezone.utc)

        # ...and neither can Bob — the cooldown is household-wide, not per person.
        try:
            await log_completion(session, contest, BOB)
            raise AssertionError("expected TooSoonError")
        except TooSoonError:
            pass


async def test_cooldown_elapsed_allows_logging_again(test_engine):
    async with _session(test_engine) as session:
        await _seed_users(session, [(ALICE, "Alice")])
        contest = ContestDuty(
            title="Dishwasher", icon="🍽️", created_by_id=ALICE, min_interval_minutes=60
        )
        session.add(contest)
        await session.flush()
        # Last log was 2 hours ago — the 60-minute cooldown has elapsed.
        session.add(
            ContestLogEntry(
                contest_duty_id=contest.id,
                user_id=ALICE,
                logged_at=datetime.now(timezone.utc) - timedelta(hours=2),
            )
        )
        await session.commit()

        assert await next_log_allowed_at(session, contest) is None
        entry = await log_completion(session, contest, ALICE)
        assert entry.id is not None


async def test_zero_interval_means_no_cooldown(test_engine):
    async with _session(test_engine) as session:
        await _seed_users(session, [(ALICE, "Alice")])
        contest = ContestDuty(title="Dishwasher", icon="🍽️", created_by_id=ALICE, min_interval_minutes=0)
        session.add(contest)
        await session.commit()

        await log_completion(session, contest, ALICE)
        await log_completion(session, contest, ALICE)
        assert await next_log_allowed_at(session, contest) is None


async def test_finalize_creates_result_per_active_contest_none_for_inactive(test_engine, monkeypatch):
    await _disable_real_push(monkeypatch)
    async with _session(test_engine) as session:
        await _seed_users(session, [(ALICE, "Alice")])
        active = ContestDuty(title="Dishwasher", icon="🍽️", created_by_id=ALICE, is_active=True)
        inactive = ContestDuty(title="Old chore", icon="🧹", created_by_id=ALICE, is_active=False)
        session.add_all([active, inactive])
        await session.flush()
        session.add(ContestLogEntry(contest_duty_id=active.id, user_id=ALICE, logged_at=_at(5)))
        session.add(ContestLogEntry(contest_duty_id=inactive.id, user_id=ALICE, logged_at=_at(5)))
        await session.commit()

        await run_award_cycle_tick(session, as_of=date(CYCLE_MONTH.year, CYCLE_MONTH.month, 15))
        cycle = (await session.execute(select(AwardCycle))).scalar_one()
        reveal_date = date(2026, 4, 30)  # safely past the real reveal date
        await run_award_cycle_tick(session, as_of=reveal_date)

        results = list(
            (await session.execute(select(ContestAwardResult).where(ContestAwardResult.cycle_id == cycle.id))).scalars()
        )
        assert len(results) == 1
        assert results[0].contest_duty_id == active.id
        assert results[0].winner_id == ALICE
        assert results[0].completion_count == 1


async def test_finalize_gives_independent_winners_per_contest(test_engine, monkeypatch):
    await _disable_real_push(monkeypatch)
    async with _session(test_engine) as session:
        await _seed_users(session, [(ALICE, "Alice"), (BOB, "Bob")])
        contest_a = ContestDuty(title="Dishwasher", icon="🍽️", created_by_id=ALICE)
        contest_b = ContestDuty(title="Recycling", icon="♻️", created_by_id=ALICE)
        session.add_all([contest_a, contest_b])
        await session.flush()
        # Alice wins contest A (2 vs 1), Bob wins contest B (2 vs 1) — must not blend.
        session.add_all(
            [
                ContestLogEntry(contest_duty_id=contest_a.id, user_id=ALICE, logged_at=_at(5)),
                ContestLogEntry(contest_duty_id=contest_a.id, user_id=ALICE, logged_at=_at(6)),
                ContestLogEntry(contest_duty_id=contest_a.id, user_id=BOB, logged_at=_at(5)),
                ContestLogEntry(contest_duty_id=contest_b.id, user_id=BOB, logged_at=_at(5)),
                ContestLogEntry(contest_duty_id=contest_b.id, user_id=BOB, logged_at=_at(6)),
                ContestLogEntry(contest_duty_id=contest_b.id, user_id=ALICE, logged_at=_at(5)),
            ]
        )
        await session.commit()

        await run_award_cycle_tick(session, as_of=date(CYCLE_MONTH.year, CYCLE_MONTH.month, 15))
        cycle = (await session.execute(select(AwardCycle))).scalar_one()
        await run_award_cycle_tick(session, as_of=date(2026, 4, 30))

        results = {
            r.contest_duty_id: r
            for r in (
                await session.execute(select(ContestAwardResult).where(ContestAwardResult.cycle_id == cycle.id))
            ).scalars()
        }
        assert results[contest_a.id].winner_id == ALICE
        assert results[contest_a.id].completion_count == 2
        assert results[contest_b.id].winner_id == BOB
        assert results[contest_b.id].completion_count == 2


async def test_finalize_contest_with_zero_activity_has_no_winner(test_engine, monkeypatch):
    await _disable_real_push(monkeypatch)
    async with _session(test_engine) as session:
        await _seed_users(session, [(ALICE, "Alice")])
        contest = ContestDuty(title="Dishwasher", icon="🍽️", created_by_id=ALICE)
        session.add(contest)
        await session.commit()

        await run_award_cycle_tick(session, as_of=date(CYCLE_MONTH.year, CYCLE_MONTH.month, 15))
        cycle = (await session.execute(select(AwardCycle))).scalar_one()
        await run_award_cycle_tick(session, as_of=date(2026, 4, 30))

        result = (
            await session.execute(select(ContestAwardResult).where(ContestAwardResult.cycle_id == cycle.id))
        ).scalar_one()
        assert result.winner_id is None
        assert result.completion_count is None


async def test_finalize_is_idempotent_for_contest_results(test_engine, monkeypatch):
    await _disable_real_push(monkeypatch)
    async with _session(test_engine) as session:
        await _seed_users(session, [(ALICE, "Alice")])
        contest = ContestDuty(title="Dishwasher", icon="🍽️", created_by_id=ALICE)
        session.add(contest)
        await session.flush()
        session.add(ContestLogEntry(contest_duty_id=contest.id, user_id=ALICE, logged_at=_at(5)))
        await session.commit()

        await run_award_cycle_tick(session, as_of=date(CYCLE_MONTH.year, CYCLE_MONTH.month, 15))
        reveal_date = date(2026, 4, 30)
        await run_award_cycle_tick(session, as_of=reveal_date)
        await run_award_cycle_tick(session, as_of=reveal_date)

        results = list((await session.execute(select(ContestAwardResult))).scalars())
        assert len(results) == 1


async def test_compute_contest_winner_tie_break_earliest_wins(test_engine):
    async with _session(test_engine) as session:
        await _seed_users(session, [(ALICE, "Alice"), (BOB, "Bob")])
        contest = ContestDuty(title="Dishwasher", icon="🍽️", created_by_id=ALICE)
        session.add(contest)
        await session.flush()
        # Both reach 2 completions; Alice reaches it first (day 6 vs day 7).
        session.add_all(
            [
                ContestLogEntry(contest_duty_id=contest.id, user_id=ALICE, logged_at=_at(5)),
                ContestLogEntry(contest_duty_id=contest.id, user_id=ALICE, logged_at=_at(6)),
                ContestLogEntry(contest_duty_id=contest.id, user_id=BOB, logged_at=_at(5)),
                ContestLogEntry(contest_duty_id=contest.id, user_id=BOB, logged_at=_at(7)),
            ]
        )
        await session.commit()

        month_start, month_end = current_month_bounds(CYCLE_MONTH)
        winner, count = await _compute_contest_winner(session, contest.id, month_start, month_end)
        assert winner == ALICE
        assert count == 2
