import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.backend import current_active_user, current_superuser
from app.db import get_session
from app.models.awards import AwardCategorySuggestion, AwardCategoryVote, AwardCycle, AwardCyclePhase
from app.models.user import User
from app.schemas.awards import (
    AwardCurrentStateOut,
    AwardCycleOut,
    AwardSuggestionCreate,
    AwardSummaryOut,
    AwardTickIn,
    AwardVetoIn,
    AwardVoteIn,
    AwardVoteTallyOut,
    MemberAwardBadgeOut,
    MemberAwardHistoryOut,
)
from app.services.awards import (
    get_current_cycle,
    get_latest_decided_cycle,
    get_live_vote_tally,
    get_my_suggestion_submitted,
    get_my_vote,
    list_member_badges,
    run_award_cycle_tick,
)
from app.timeutils import today

router = APIRouter(prefix="/api/awards", tags=["awards"], dependencies=[Depends(current_active_user)])


def _build_cycle_out(cycle: AwardCycle) -> AwardCycleOut:
    suggestion = cycle.drawn_suggestion
    return AwardCycleOut(
        id=cycle.id,
        month=cycle.month,
        phase=cycle.phase.value,
        drawn_category_title=suggestion.title if suggestion else None,
        drawn_category_emoji=suggestion.emoji if suggestion else None,
        drawn_category_suggested_by_id=suggestion.suggested_by_id if suggestion else None,
        duty_master_winner_id=cycle.duty_master_winner_id,
        duty_master_win_count=cycle.duty_master_win_count,
        community_award_winner_id=cycle.community_award_winner_id,
        community_award_vote_count=cycle.community_award_vote_count,
        community_award_vetoed=cycle.community_award_vetoed,
        finalized_at=cycle.finalized_at,
    )


@router.get("/summary", response_model=AwardSummaryOut)
async def get_summary(
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_session),
):
    # A pure read — state transitions happen only via the scheduler/cron tick (or
    # admin/tick), same as every other tick-driven feature in this app (see
    # app/services/reminders.py). This is never more than one tick interval stale.
    current = await get_current_cycle(session)
    current_out = None
    if current is not None:
        votes = []
        if current.phase == AwardCyclePhase.voting:
            tally = await get_live_vote_tally(session, current.id)
            votes = [AwardVoteTallyOut(candidate_user_id=uid, vote_count=count) for uid, count in tally]
        current_out = AwardCurrentStateOut(
            **_build_cycle_out(current).model_dump(),
            my_suggestion_submitted=await get_my_suggestion_submitted(session, current.id, user.id),
            my_vote_candidate_id=await get_my_vote(session, current.id, user.id),
            votes=votes,
        )

    latest_decided = await get_latest_decided_cycle(session)
    latest_decided_out = _build_cycle_out(latest_decided) if latest_decided is not None else None

    return AwardSummaryOut(current=current_out, latest_decided=latest_decided_out)


@router.post("/suggestions", status_code=201)
async def create_suggestion(
    data: AwardSuggestionCreate,
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_session),
):
    cycle = await get_current_cycle(session)
    if cycle is None or cycle.phase != AwardCyclePhase.suggesting:
        raise HTTPException(status_code=400, detail="SUGGESTION_WINDOW_CLOSED")

    suggestion = AwardCategorySuggestion(
        cycle_id=cycle.id, title=data.title, emoji=data.emoji, suggested_by_id=user.id
    )
    session.add(suggestion)
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(status_code=409, detail="ALREADY_SUGGESTED") from None
    return {"ok": True}


@router.put("/cycles/{cycle_id}/vote")
async def vote(
    cycle_id: uuid.UUID,
    data: AwardVoteIn,
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_session),
):
    cycle = (await session.execute(select(AwardCycle).where(AwardCycle.id == cycle_id))).scalar_one_or_none()
    if cycle is None:
        raise HTTPException(status_code=404, detail="CYCLE_NOT_FOUND")
    if cycle.phase != AwardCyclePhase.voting or cycle.drawn_suggestion_id is None:
        raise HTTPException(status_code=400, detail="VOTING_NOT_OPEN")

    candidate_exists = (
        await session.execute(
            select(User.id).where(User.id == data.candidate_user_id, User.is_active.is_(True))
        )
    ).scalar_one_or_none()
    if candidate_exists is None:
        raise HTTPException(status_code=422, detail="INVALID_CANDIDATE")

    existing = (
        await session.execute(
            select(AwardCategoryVote).where(
                AwardCategoryVote.cycle_id == cycle_id, AwardCategoryVote.voter_id == user.id
            )
        )
    ).scalar_one_or_none()
    if existing is None:
        session.add(AwardCategoryVote(cycle_id=cycle_id, voter_id=user.id, candidate_id=data.candidate_user_id))
    else:
        existing.candidate_id = data.candidate_user_id
        existing.voted_at = datetime.now(timezone.utc)
    await session.commit()
    return {"ok": True}


@router.get("/members/{user_id}/history", response_model=MemberAwardHistoryOut)
async def get_member_history(user_id: uuid.UUID, session: AsyncSession = Depends(get_session)):
    badges = await list_member_badges(session, user_id)
    return MemberAwardHistoryOut(
        user_id=user_id, badges=[MemberAwardBadgeOut(**badge) for badge in badges]
    )


@router.post("/cycles/{cycle_id}/veto")
async def veto(
    cycle_id: uuid.UUID,
    data: AwardVetoIn,
    admin: User = Depends(current_superuser),
    session: AsyncSession = Depends(get_session),
):
    cycle = (await session.execute(select(AwardCycle).where(AwardCycle.id == cycle_id))).scalar_one_or_none()
    if cycle is None:
        raise HTTPException(status_code=404, detail="CYCLE_NOT_FOUND")
    if cycle.drawn_suggestion_id is None:
        raise HTTPException(status_code=400, detail="NOTHING_DRAWN_YET")
    if cycle.community_award_vetoed:
        raise HTTPException(status_code=400, detail="ALREADY_VETOED")

    cycle.community_award_vetoed = True
    cycle.community_award_veto_by_id = admin.id
    cycle.community_award_veto_at = datetime.now(timezone.utc)
    cycle.community_award_veto_reason = data.reason
    # If this cycle was already decided before the veto, undo the recorded winner too —
    # a veto means no one is credited with the community award for this cycle, full stop.
    cycle.community_award_winner_id = None
    cycle.community_award_vote_count = None
    await session.commit()
    return {"ok": True}


@router.post("/admin/tick")
async def admin_tick(
    data: AwardTickIn,
    admin: User = Depends(current_superuser),
    session: AsyncSession = Depends(get_session),
):
    await run_award_cycle_tick(session, as_of=data.as_of or today())
    return {"ok": True}
