import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.backend import current_active_user
from app.db import get_session
from app.models.contests import ContestDuty
from app.models.user import User
from app.schemas.contests import (
    ContestDutyCreate,
    ContestDutyOut,
    ContestDutyUpdate,
    ContestLogEntryOut,
    ContestSummaryEntryOut,
)
from app.services.contests import (
    TooSoonError,
    create_contest_duty,
    delete_log_entry,
    list_active_contests_for_user,
    log_completion,
    update_contest_duty,
)

router = APIRouter(prefix="/api/contests", tags=["contests"], dependencies=[Depends(current_active_user)])


async def _load_contest_or_404(session: AsyncSession, contest_id: uuid.UUID) -> ContestDuty:
    result = await session.execute(select(ContestDuty).where(ContestDuty.id == contest_id))
    contest = result.scalar_one_or_none()
    if contest is None:
        raise HTTPException(status_code=404, detail="CONTEST_NOT_FOUND")
    return contest


@router.get("", response_model=list[ContestSummaryEntryOut])
async def list_contests(
    home_only: bool = Query(False, description="Only contests flagged to show on the Home screen"),
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_session),
):
    entries = await list_active_contests_for_user(session, user.id, home_only=home_only)
    return [
        ContestSummaryEntryOut(
            id=entry["contest"].id,
            title=entry["contest"].title,
            description=entry["contest"].description,
            icon=entry["contest"].icon,
            min_interval_minutes=entry["contest"].min_interval_minutes,
            show_on_home=entry["contest"].show_on_home,
            is_active=entry["contest"].is_active,
            created_by_id=entry["contest"].created_by_id,
            created_at=entry["contest"].created_at,
            my_count=entry["my_count"],
            next_log_allowed_at=entry["next_log_allowed_at"],
        )
        for entry in entries
    ]


@router.post("", response_model=ContestDutyOut, status_code=201)
async def create_contest(
    data: ContestDutyCreate,
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_session),
):
    return await create_contest_duty(
        session,
        title=data.title,
        description=data.description,
        icon=data.icon,
        min_interval_minutes=data.min_interval_minutes,
        show_on_home=data.show_on_home,
        created_by_id=user.id,
    )


@router.patch("/{contest_id}", response_model=ContestDutyOut)
async def update_contest(
    contest_id: uuid.UUID, data: ContestDutyUpdate, session: AsyncSession = Depends(get_session)
):
    contest = await _load_contest_or_404(session, contest_id)
    return await update_contest_duty(
        session,
        contest,
        title=data.title,
        description=data.description,
        icon=data.icon,
        min_interval_minutes=data.min_interval_minutes,
        show_on_home=data.show_on_home,
        is_active=data.is_active,
    )


@router.post("/{contest_id}/log", response_model=ContestLogEntryOut, status_code=201)
async def log_contest_completion(
    contest_id: uuid.UUID,
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_session),
):
    contest = await _load_contest_or_404(session, contest_id)
    try:
        return await log_completion(session, contest, user.id)
    except TooSoonError as exc:
        raise HTTPException(
            status_code=429,
            detail={"code": "LOG_TOO_SOON", "ready_at": exc.ready_at.isoformat()},
        ) from None


@router.delete("/{contest_id}/log/{entry_id}", status_code=204)
async def delete_contest_log_entry(
    contest_id: uuid.UUID,
    entry_id: uuid.UUID,
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_session),
):
    try:
        await delete_log_entry(session, contest_id, entry_id, user)
    except LookupError:
        raise HTTPException(status_code=404, detail="LOG_ENTRY_NOT_FOUND") from None
    except PermissionError:
        raise HTTPException(status_code=403, detail="NOT_YOUR_LOG_ENTRY") from None
