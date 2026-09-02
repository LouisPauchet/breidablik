import random
import uuid
from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

import app.services.push as push_module
from app.models.awards import AwardCategorySuggestion, AwardCategoryVote, AwardCycle, AwardCyclePhase
from app.models.duty import DutyOccurrence
from app.models.notification import Notification
from app.models.user import User
from app.services.awards import (
    _first_saturday,
    _reveal_date,
    _voting_start_day,
    compute_draw_weights,
    run_award_cycle_tick,
)

ALICE = uuid.uuid4()
BOB = uuid.uuid4()
CAROL = uuid.uuid4()


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


# A month picked so its voting-start day and reveal date are unambiguous in test assertions.
CYCLE_MONTH = date(2026, 3, 1)  # March 2026: 31 days -> voting starts day 26
VOTING_START_DAY = _voting_start_day(CYCLE_MONTH.year, CYCLE_MONTH.month)
REVEAL_DATE = _reveal_date(CYCLE_MONTH)


async def test_no_cycle_created_before_suggestion_window(test_engine, monkeypatch):
    await _disable_real_push(monkeypatch)
    async with _session(test_engine) as session:
        await run_award_cycle_tick(session, as_of=date(CYCLE_MONTH.year, CYCLE_MONTH.month, 10))
        result = await session.execute(select(AwardCycle))
        assert list(result.scalars()) == []


async def test_suggestion_window_opens_on_day_15_and_is_idempotent(test_engine, monkeypatch):
    await _disable_real_push(monkeypatch)
    async with _session(test_engine) as session:
        await _seed_users(session, [(ALICE, "Alice")])
        on_date = date(CYCLE_MONTH.year, CYCLE_MONTH.month, 15)

        await run_award_cycle_tick(session, as_of=on_date)
        await run_award_cycle_tick(session, as_of=on_date)

        cycles = list((await session.execute(select(AwardCycle))).scalars())
        assert len(cycles) == 1
        assert cycles[0].month == CYCLE_MONTH
        assert cycles[0].phase == AwardCyclePhase.suggesting
        assert cycles[0].suggestion_window_opened_at is not None

        notifications = list((await session.execute(select(Notification))).scalars())
        assert len(notifications) == 1
        assert notifications[0].kind == "award_suggest_open"


async def test_voting_window_draws_a_suggestion_and_is_idempotent(test_engine, monkeypatch):
    await _disable_real_push(monkeypatch)
    async with _session(test_engine) as session:
        await _seed_users(session, [(ALICE, "Alice"), (BOB, "Bob")])
        await run_award_cycle_tick(session, as_of=date(CYCLE_MONTH.year, CYCLE_MONTH.month, 15))

        cycle = (await session.execute(select(AwardCycle))).scalar_one()
        session.add(
            AwardCategorySuggestion(cycle_id=cycle.id, title="Best Cook", emoji="🍳", suggested_by_id=ALICE)
        )
        await session.commit()

        voting_date = date(CYCLE_MONTH.year, CYCLE_MONTH.month, VOTING_START_DAY)
        await run_award_cycle_tick(session, as_of=voting_date)
        await run_award_cycle_tick(session, as_of=voting_date)

        await session.refresh(cycle)
        assert cycle.phase == AwardCyclePhase.voting
        assert cycle.drawn_suggestion_id is not None
        assert cycle.voting_window_opened_at is not None

        vote_notifications = [
            n for n in (await session.execute(select(Notification))).scalars() if n.kind == "award_vote_open"
        ]
        # One per active user (Alice + Bob) — and unchanged by the second, idempotent tick.
        assert len(vote_notifications) == 2
        assert all("Best Cook" in n.title for n in vote_notifications)


async def test_voting_window_opens_with_no_winner_when_nobody_suggested(test_engine, monkeypatch):
    await _disable_real_push(monkeypatch)
    async with _session(test_engine) as session:
        await _seed_users(session, [(ALICE, "Alice")])
        await run_award_cycle_tick(session, as_of=date(CYCLE_MONTH.year, CYCLE_MONTH.month, 15))

        voting_date = date(CYCLE_MONTH.year, CYCLE_MONTH.month, VOTING_START_DAY)
        await run_award_cycle_tick(session, as_of=voting_date)

        cycle = (await session.execute(select(AwardCycle))).scalar_one()
        assert cycle.phase == AwardCyclePhase.voting
        assert cycle.drawn_suggestion_id is None

        assert not [
            n for n in (await session.execute(select(Notification))).scalars() if n.kind == "award_vote_open"
        ]


async def test_finalization_computes_duty_master_and_tallies_votes(test_engine, monkeypatch):
    await _disable_real_push(monkeypatch)
    async with _session(test_engine) as session:
        await _seed_users(session, [(ALICE, "Alice"), (BOB, "Bob")])
        await run_award_cycle_tick(session, as_of=date(CYCLE_MONTH.year, CYCLE_MONTH.month, 15))
        cycle = (await session.execute(select(AwardCycle))).scalar_one()

        session.add(
            AwardCategorySuggestion(cycle_id=cycle.id, title="Best Cook", emoji="🍳", suggested_by_id=ALICE)
        )
        await session.commit()
        await run_award_cycle_tick(session, as_of=date(CYCLE_MONTH.year, CYCLE_MONTH.month, VOTING_START_DAY))

        # Alice: 2 on-time completions. Bob: 1 on-time, 1 late (doesn't count), 1 undone.
        session.add_all(
            [
                DutyOccurrence(
                    duty_id=uuid.uuid4(),
                    due_date=CYCLE_MONTH.replace(day=5),
                    period_index=0,
                    assigned_user_id=ALICE,
                    is_done=True,
                    done_by_id=ALICE,
                    done_at=datetime(CYCLE_MONTH.year, CYCLE_MONTH.month, 5, 8, tzinfo=timezone.utc),
                ),
                DutyOccurrence(
                    duty_id=uuid.uuid4(),
                    due_date=CYCLE_MONTH.replace(day=6),
                    period_index=0,
                    assigned_user_id=ALICE,
                    is_done=True,
                    done_by_id=ALICE,
                    done_at=datetime(CYCLE_MONTH.year, CYCLE_MONTH.month, 6, 8, tzinfo=timezone.utc),
                ),
                DutyOccurrence(
                    duty_id=uuid.uuid4(),
                    due_date=CYCLE_MONTH.replace(day=5),
                    period_index=0,
                    assigned_user_id=BOB,
                    is_done=True,
                    done_by_id=BOB,
                    done_at=datetime(CYCLE_MONTH.year, CYCLE_MONTH.month, 5, 8, tzinfo=timezone.utc),
                ),
                DutyOccurrence(
                    duty_id=uuid.uuid4(),
                    due_date=CYCLE_MONTH.replace(day=5),
                    period_index=0,
                    assigned_user_id=BOB,
                    is_done=True,
                    done_by_id=BOB,
                    done_at=datetime(CYCLE_MONTH.year, CYCLE_MONTH.month, 8, 8, tzinfo=timezone.utc),  # late
                ),
                DutyOccurrence(
                    duty_id=uuid.uuid4(), due_date=CYCLE_MONTH.replace(day=9), period_index=0, assigned_user_id=BOB
                ),
            ]
        )
        session.add(AwardCategoryVote(cycle_id=cycle.id, voter_id=ALICE, candidate_id=BOB))
        session.add(AwardCategoryVote(cycle_id=cycle.id, voter_id=BOB, candidate_id=BOB))
        await session.commit()

        await run_award_cycle_tick(session, as_of=REVEAL_DATE)

        await session.refresh(cycle)
        assert cycle.phase == AwardCyclePhase.decided
        assert cycle.finalized_at is not None
        assert cycle.duty_master_winner_id == ALICE
        assert cycle.duty_master_win_count == 2
        assert cycle.community_award_winner_id == BOB
        assert cycle.community_award_vote_count == 2

        results = [
            n for n in (await session.execute(select(Notification))).scalars() if n.kind == "award_results"
        ]
        # One per active user (Alice + Bob).
        assert len(results) == 2

        # Idempotent — re-ticking after reveal doesn't double-finalize or re-notify.
        await run_award_cycle_tick(session, as_of=REVEAL_DATE)
        results_after = [
            n for n in (await session.execute(select(Notification))).scalars() if n.kind == "award_results"
        ]
        assert len(results_after) == 2


async def test_veto_before_reveal_prevents_a_community_winner(test_engine, monkeypatch):
    await _disable_real_push(monkeypatch)
    async with _session(test_engine) as session:
        await _seed_users(session, [(ALICE, "Alice"), (BOB, "Bob")])
        await run_award_cycle_tick(session, as_of=date(CYCLE_MONTH.year, CYCLE_MONTH.month, 15))
        cycle = (await session.execute(select(AwardCycle))).scalar_one()
        session.add(
            AwardCategorySuggestion(cycle_id=cycle.id, title="Best Cook", emoji="🍳", suggested_by_id=ALICE)
        )
        await session.commit()
        await run_award_cycle_tick(session, as_of=date(CYCLE_MONTH.year, CYCLE_MONTH.month, VOTING_START_DAY))

        session.add(AwardCategoryVote(cycle_id=cycle.id, voter_id=BOB, candidate_id=ALICE))
        await session.refresh(cycle)
        cycle.community_award_vetoed = True
        await session.commit()

        await run_award_cycle_tick(session, as_of=REVEAL_DATE)

        await session.refresh(cycle)
        assert cycle.phase == AwardCyclePhase.decided
        assert cycle.community_award_winner_id is None
        assert cycle.community_award_vote_count is None


async def test_multi_month_backfill_finalizes_skipped_months(test_engine, monkeypatch):
    await _disable_real_push(monkeypatch)
    async with _session(test_engine) as session:
        await _seed_users(session, [(ALICE, "Alice")])
        await run_award_cycle_tick(session, as_of=date(2026, 1, 20))

        # Simulate 3 months of downtime: the next tick lands in April with no ticks in between.
        far_future = date(2026, 4, 20)
        await run_award_cycle_tick(session, as_of=far_future)
        await run_award_cycle_tick(session, as_of=far_future)  # settle any just-created backfill rows

        cycles = {c.month: c for c in (await session.execute(select(AwardCycle))).scalars()}
        assert set(cycles) == {date(2026, 1, 1), date(2026, 2, 1), date(2026, 3, 1), date(2026, 4, 1)}
        assert cycles[date(2026, 1, 1)].phase == AwardCyclePhase.decided
        assert cycles[date(2026, 2, 1)].phase == AwardCyclePhase.decided
        assert cycles[date(2026, 3, 1)].phase == AwardCyclePhase.decided
        assert cycles[date(2026, 2, 1)].suggestion_window_opened_at is None
        assert cycles[date(2026, 4, 1)].phase == AwardCyclePhase.suggesting


def test_compute_draw_weights_clamped_1_to_6():
    suggestions = [
        SimpleNamespace(suggested_by_id=ALICE),
        SimpleNamespace(suggested_by_id=BOB),
        SimpleNamespace(suggested_by_id=CAROL),
    ]
    current_month = date(2026, 6, 1)
    last_drawn = {
        ALICE: date(2026, 5, 1),  # 1 month ago -> weight 1
        BOB: date(2025, 1, 1),  # far outside lookback -> clamped to 6
        # CAROL never drawn -> weight 6
    }
    weights = compute_draw_weights(suggestions, last_drawn, current_month)
    assert weights == [1, 6, 6]


def test_weighted_draw_favors_less_recently_drawn_suggester():
    suggestions = [SimpleNamespace(id="low", label="low"), SimpleNamespace(id="high", label="high")]
    weights = [1, 6]
    counts = {"low": 0, "high": 0}
    for _ in range(3000):
        choice = random.choices(suggestions, weights=weights, k=1)[0]
        counts[choice.label] += 1
    high_share = counts["high"] / 3000
    assert 0.70 < high_share < 0.95


def test_first_saturday_and_reveal_date():
    # March 1 2026 is a Sunday -> first Saturday is March 7.
    assert _first_saturday(2026, 3) == date(2026, 3, 7)
    assert _reveal_date(date(2026, 2, 1)) == date(2026, 3, 7)
    assert _reveal_date(date(2026, 12, 1)) == _first_saturday(2027, 1)


def test_voting_start_day_matches_month_length_with_february_exception():
    assert _voting_start_day(2026, 4) == 25  # 30-day month
    assert _voting_start_day(2026, 1) == 26  # 31-day month
    assert _voting_start_day(2026, 2) == 25  # February override
    assert _voting_start_day(2024, 2) == 25  # leap February, still 25
