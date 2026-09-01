import uuid
from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.absence import Absence


async def load_active_absences_by_user(
    session: AsyncSession, user_ids: list[uuid.UUID]
) -> dict[uuid.UUID, list[Absence]]:
    if not user_ids:
        return {}
    result = await session.execute(select(Absence).where(Absence.user_id.in_(user_ids)))
    by_user: dict[uuid.UUID, list[Absence]] = {}
    for absence in result.scalars():
        by_user.setdefault(absence.user_id, []).append(absence)
    return by_user


async def load_auto_reassign_absences_by_user(
    session: AsyncSession, user_ids: list[uuid.UUID]
) -> dict[uuid.UUID, list[Absence]]:
    if not user_ids:
        return {}
    result = await session.execute(
        select(Absence).where(Absence.user_id.in_(user_ids), Absence.auto_reassign.is_(True))
    )
    by_user: dict[uuid.UUID, list[Absence]] = {}
    for absence in result.scalars():
        by_user.setdefault(absence.user_id, []).append(absence)
    return by_user


def is_user_away(
    absences_by_user: dict[uuid.UUID, list[Absence]], user_id: uuid.UUID, on_date: date
) -> bool:
    return any(
        absence.start_date <= on_date <= absence.end_date
        for absence in absences_by_user.get(user_id, [])
    )
