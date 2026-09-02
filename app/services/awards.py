"""Monthly awards state machine: "Duty Master" (objective, computed from DutyOccurrence
completion history) and the "community award" (member-suggested category, drawn at random,
voted on, vetoable by an admin). Driven by the same idempotent-tick pattern as
app/services/reminders.py — see run_award_cycle_tick, called from both app/main.py's
scheduler and app/routers/internal.py's cron endpoint.

Cycle timeline for a given calendar month (e.g. October):
  - Suggestion window: days 15-25 of October.
  - Voting window: opens right after (day 25/26, or the 25th for February specifically,
    since the general formula would land before suggestions even close in that short month)
    and runs into November.
  - Reveal: the first Saturday of November — Duty Master and the community award are both
    decided at this same moment.
"""

import calendar
import random
import uuid
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import get_settings
from app.models.awards import AwardCategorySuggestion, AwardCategoryVote, AwardCycle, AwardCyclePhase
from app.models.duty import DutyOccurrence
from app.services.notifications import (
    notify_award_results_decided,
    notify_award_suggestion_window_open,
    notify_award_voting_window_open,
)
from app.timeutils import today

SUGGESTION_START_DAY = 15
DRAW_LOOKBACK_MONTHS = 6


def _next_month(d: date) -> date:
    if d.month == 12:
        return date(d.year + 1, 1, 1)
    return date(d.year, d.month + 1, 1)


def _voting_start_day(year: int, month: int) -> int:
    if month == 2:
        return 25
    return calendar.monthrange(year, month)[1] - 5


def _first_saturday(year: int, month: int) -> date:
    first = date(year, month, 1)
    return first + timedelta(days=(5 - first.weekday()) % 7)


def _reveal_date(cycle_month: date) -> date:
    next_month = _next_month(cycle_month)
    return _first_saturday(next_month.year, next_month.month)


def compute_draw_weights(
    suggestions: list[AwardCategorySuggestion],
    last_drawn_by_suggester: dict[uuid.UUID, date],
    current_month: date,
) -> list[int]:
    """Weight = months since that suggester's last drawn suggestion, clamped 1-6 (never
    drawn, or not within the lookback, gets the max weight) — spreads the draw around over
    time without hard-excluding anyone.
    """
    weights = []
    for suggestion in suggestions:
        last = last_drawn_by_suggester.get(suggestion.suggested_by_id)
        if last is None:
            weights.append(DRAW_LOOKBACK_MONTHS)
        else:
            months_since = (current_month.year - last.year) * 12 + (current_month.month - last.month)
            weights.append(max(1, min(DRAW_LOOKBACK_MONTHS, months_since)))
    return weights


async def _recent_draws_by_suggester(session: AsyncSession, before_month: date) -> dict[uuid.UUID, date]:
    lookback_year = before_month.year
    lookback_month = before_month.month - DRAW_LOOKBACK_MONTHS
    while lookback_month <= 0:
        lookback_month += 12
        lookback_year -= 1
    lookback_start = date(lookback_year, lookback_month, 1)

    result = await session.execute(
        select(AwardCategorySuggestion.suggested_by_id, func.max(AwardCycle.month))
        .join(AwardCycle, AwardCycle.drawn_suggestion_id == AwardCategorySuggestion.id)
        .where(AwardCycle.month >= lookback_start, AwardCycle.month < before_month)
        .group_by(AwardCategorySuggestion.suggested_by_id)
    )
    return dict(result.all())


def _reached_winning_tally_first(counts: dict[uuid.UUID, list[datetime]], max_count: int) -> uuid.UUID:
    tied = [uid for uid, times in counts.items() if len(times) == max_count]
    if len(tied) == 1:
        return tied[0]

    def reached_at(uid: uuid.UUID) -> datetime:
        return sorted(counts[uid])[max_count - 1]

    return min(tied, key=lambda uid: (reached_at(uid), uid))


async def _compute_duty_master(
    session: AsyncSession, month_start: date, month_end: date
) -> tuple[uuid.UUID | None, int | None]:
    zone = get_settings().zone_info
    result = await session.execute(
        select(DutyOccurrence).where(
            DutyOccurrence.due_date >= month_start,
            DutyOccurrence.due_date <= month_end,
            DutyOccurrence.is_done.is_(True),
            DutyOccurrence.done_by_id.is_not(None),
            DutyOccurrence.done_at.is_not(None),
        )
    )
    on_time_by_user: dict[uuid.UUID, list[datetime]] = defaultdict(list)
    for occurrence in result.scalars():
        done_at = occurrence.done_at
        if done_at.tzinfo is None:
            done_at = done_at.replace(tzinfo=timezone.utc)
        if done_at.astimezone(zone).date() <= occurrence.due_date:
            on_time_by_user[occurrence.done_by_id].append(done_at)

    if not on_time_by_user:
        return None, None

    max_count = max(len(times) for times in on_time_by_user.values())
    winner = _reached_winning_tally_first(on_time_by_user, max_count)
    return winner, max_count


async def _tally_votes(session: AsyncSession, cycle_id: uuid.UUID) -> tuple[uuid.UUID | None, int | None]:
    result = await session.execute(select(AwardCategoryVote).where(AwardCategoryVote.cycle_id == cycle_id))
    by_candidate: dict[uuid.UUID, list[datetime]] = defaultdict(list)
    for vote in result.scalars():
        by_candidate[vote.candidate_id].append(vote.voted_at)

    if not by_candidate:
        return None, None

    max_count = max(len(votes) for votes in by_candidate.values())
    winner = _reached_winning_tally_first(by_candidate, max_count)
    return winner, max_count


async def _finalize_cycle(session: AsyncSession, cycle: AwardCycle) -> None:
    month_end = _next_month(cycle.month) - timedelta(days=1)
    winner_id, win_count = await _compute_duty_master(session, cycle.month, month_end)
    cycle.duty_master_winner_id = winner_id
    cycle.duty_master_win_count = win_count

    if cycle.drawn_suggestion_id is not None and not cycle.community_award_vetoed:
        winner_id2, vote_count = await _tally_votes(session, cycle.id)
        cycle.community_award_winner_id = winner_id2
        cycle.community_award_vote_count = vote_count

    cycle.phase = AwardCyclePhase.decided
    cycle.finalized_at = datetime.now(timezone.utc)
    await session.commit()
    await notify_award_results_decided(session, cycle)


async def _finalize_due_cycles(session: AsyncSession, on_date: date) -> None:
    result = await session.execute(
        select(AwardCycle)
        .options(selectinload(AwardCycle.drawn_suggestion))
        .where(AwardCycle.finalized_at.is_(None))
    )
    for cycle in result.scalars():
        if on_date >= _reveal_date(cycle.month):
            await _finalize_cycle(session, cycle)


async def _create_cycle_row(session: AsyncSession, month: date, *, is_current: bool) -> None:
    cycle = AwardCycle(month=month)
    if is_current:
        cycle.suggestion_window_opened_at = datetime.now(timezone.utc)
    session.add(cycle)
    try:
        await session.commit()
    except IntegrityError:
        # Another concurrent worker already created this month's row — nothing left to do.
        await session.rollback()
        return
    if is_current:
        await notify_award_suggestion_window_open(session, cycle)


async def _open_suggestion_windows(session: AsyncSession, on_date: date) -> None:
    current_month = date(on_date.year, on_date.month, 1)
    latest_month = (await session.execute(select(func.max(AwardCycle.month)))).scalar_one_or_none()

    if latest_month is None:
        if on_date.day < SUGGESTION_START_DAY:
            return
        await _create_cycle_row(session, current_month, is_current=True)
        return

    # Backfill any months missed during downtime (bare rows — they never really opened for
    # suggestions, and get picked up and finalized by _finalize_due_cycles with no community
    # award, just a correctly-computed Duty Master).
    candidate = _next_month(latest_month)
    while candidate < current_month:
        await _create_cycle_row(session, candidate, is_current=False)
        candidate = _next_month(candidate)

    if candidate == current_month and on_date.day >= SUGGESTION_START_DAY:
        await _create_cycle_row(session, candidate, is_current=True)


async def _open_voting_window_if_due(session: AsyncSession, on_date: date) -> None:
    current_month = date(on_date.year, on_date.month, 1)
    result = await session.execute(select(AwardCycle).where(AwardCycle.month == current_month))
    cycle = result.scalar_one_or_none()
    if cycle is None or cycle.phase != AwardCyclePhase.suggesting:
        return
    if on_date.day < _voting_start_day(on_date.year, on_date.month):
        return

    suggestions = list(
        (
            await session.execute(
                select(AwardCategorySuggestion).where(AwardCategorySuggestion.cycle_id == cycle.id)
            )
        ).scalars()
    )

    drawn = None
    if suggestions:
        last_drawn_by_suggester = await _recent_draws_by_suggester(session, current_month)
        weights = compute_draw_weights(suggestions, last_drawn_by_suggester, current_month)
        drawn = random.choices(suggestions, weights=weights, k=1)[0]
        cycle.drawn_suggestion_id = drawn.id

    cycle.phase = AwardCyclePhase.voting
    cycle.voting_window_opened_at = datetime.now(timezone.utc)
    await session.commit()

    if drawn is not None:
        await notify_award_voting_window_open(session, cycle, drawn)


async def run_award_cycle_tick(session: AsyncSession, as_of: date | None = None) -> None:
    on_date = as_of or today()
    await _finalize_due_cycles(session, on_date)
    await _open_suggestion_windows(session, on_date)
    await _open_voting_window_if_due(session, on_date)


async def get_current_cycle(session: AsyncSession) -> AwardCycle | None:
    """The most recently created cycle, whatever its phase — deliberately not filtered by
    matching today's real calendar month, so this always agrees with whatever the tick has
    actually established regardless of exactly when it last ran (and, particularly for tests,
    regardless of any `as_of` override used to fast-forward it — see admin/tick).
    """
    result = await session.execute(
        select(AwardCycle)
        .options(selectinload(AwardCycle.drawn_suggestion))
        .order_by(AwardCycle.month.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def get_latest_decided_cycle(session: AsyncSession) -> AwardCycle | None:
    result = await session.execute(
        select(AwardCycle)
        .options(selectinload(AwardCycle.drawn_suggestion))
        .where(AwardCycle.phase == AwardCyclePhase.decided)
        .order_by(AwardCycle.month.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def get_live_vote_tally(session: AsyncSession, cycle_id: uuid.UUID) -> list[tuple[uuid.UUID, int]]:
    result = await session.execute(
        select(AwardCategoryVote.candidate_id, func.count())
        .where(AwardCategoryVote.cycle_id == cycle_id)
        .group_by(AwardCategoryVote.candidate_id)
    )
    return list(result.all())


async def get_my_suggestion_submitted(session: AsyncSession, cycle_id: uuid.UUID, user_id: uuid.UUID) -> bool:
    result = await session.execute(
        select(AwardCategorySuggestion.id).where(
            AwardCategorySuggestion.cycle_id == cycle_id, AwardCategorySuggestion.suggested_by_id == user_id
        )
    )
    return result.scalar_one_or_none() is not None


async def get_my_vote(session: AsyncSession, cycle_id: uuid.UUID, user_id: uuid.UUID) -> uuid.UUID | None:
    result = await session.execute(
        select(AwardCategoryVote.candidate_id).where(
            AwardCategoryVote.cycle_id == cycle_id, AwardCategoryVote.voter_id == user_id
        )
    )
    return result.scalar_one_or_none()


async def list_member_badges(session: AsyncSession, user_id: uuid.UUID) -> list[dict]:
    result = await session.execute(
        select(AwardCycle)
        .options(selectinload(AwardCycle.drawn_suggestion))
        .where(
            AwardCycle.finalized_at.is_not(None),
            (AwardCycle.duty_master_winner_id == user_id)
            | ((AwardCycle.community_award_winner_id == user_id) & AwardCycle.community_award_vetoed.is_(False)),
        )
        .order_by(AwardCycle.month.desc())
    )

    badges = []
    for cycle in result.scalars().unique():
        if cycle.duty_master_winner_id == user_id:
            badges.append({"month": cycle.month, "kind": "duty_master", "title": "Duty Master", "emoji": "🏆"})
        if cycle.community_award_winner_id == user_id and not cycle.community_award_vetoed:
            suggestion = cycle.drawn_suggestion
            badges.append(
                {
                    "month": cycle.month,
                    "kind": "community",
                    "title": suggestion.title if suggestion else None,
                    "emoji": suggestion.emoji if suggestion else None,
                }
            )
    badges.sort(key=lambda b: b["month"], reverse=True)
    return badges
