import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.backend import current_active_user
from app.db import get_session
from app.models.absence import Absence
from app.models.user import User
from app.schemas.absence import AbsenceCreate, AbsenceOut, AbsenceUpdate
from app.services.auto_reassign import reassign_occurrences_for_absence

router = APIRouter(prefix="/api/absences", tags=["absences"], dependencies=[Depends(current_active_user)])


@router.get("", response_model=list[AbsenceOut])
async def list_absences(session: AsyncSession = Depends(get_session)):
    result = await session.execute(select(Absence).order_by(Absence.start_date))
    return list(result.scalars())


@router.post("", response_model=AbsenceOut, status_code=201)
async def create_absence(
    data: AbsenceCreate,
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_session),
):
    absence = Absence(
        user_id=user.id,
        start_date=data.start_date,
        end_date=data.end_date,
        reason=data.reason,
        auto_reassign=data.auto_reassign,
    )
    session.add(absence)
    await session.commit()
    await session.refresh(absence)

    if absence.auto_reassign:
        await reassign_occurrences_for_absence(session, absence)

    return absence


async def _load_absence_or_404(session: AsyncSession, absence_id: uuid.UUID) -> Absence:
    result = await session.execute(select(Absence).where(Absence.id == absence_id))
    absence = result.scalar_one_or_none()
    if absence is None:
        raise HTTPException(status_code=404, detail="ABSENCE_NOT_FOUND")
    return absence


@router.patch("/{absence_id}", response_model=AbsenceOut)
async def update_absence(
    absence_id: uuid.UUID,
    data: AbsenceUpdate,
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_session),
):
    absence = await _load_absence_or_404(session, absence_id)
    if absence.user_id != user.id and not user.is_superuser:
        raise HTTPException(status_code=403, detail="NOT_YOUR_ABSENCE")

    new_start = data.start_date if data.start_date is not None else absence.start_date
    new_end = data.end_date if data.end_date is not None else absence.end_date
    if new_end < new_start:
        raise HTTPException(status_code=422, detail="END_BEFORE_START")
    absence.start_date = new_start
    absence.end_date = new_end
    if data.reason is not None:
        absence.reason = data.reason
    if data.auto_reassign is not None:
        absence.auto_reassign = data.auto_reassign

    await session.commit()
    await session.refresh(absence)

    if absence.auto_reassign:
        await reassign_occurrences_for_absence(session, absence)

    return absence


@router.delete("/{absence_id}", status_code=204)
async def delete_absence(
    absence_id: uuid.UUID,
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_session),
):
    absence = await _load_absence_or_404(session, absence_id)
    if absence.user_id != user.id and not user.is_superuser:
        raise HTTPException(status_code=403, detail="NOT_YOUR_ABSENCE")
    await session.delete(absence)
    await session.commit()
