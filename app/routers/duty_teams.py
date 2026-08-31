import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth.backend import current_active_user
from app.db import get_session
from app.models.duty import DutyTeam, DutyTeamMember
from app.models.user import User
from app.schemas.duty import (
    DutyTeamCreate,
    DutyTeamOut,
    DutyTeamUpdate,
    TeamAssignmentOut,
    TeamPeriodOut,
)
from app.services.duty_teams import resolve_all_current_assignments
from app.services.rotation import compute_period_index, period_bounds
from app.timeutils import today

router = APIRouter(prefix="/api/duty-teams", tags=["duty-teams"], dependencies=[Depends(current_active_user)])


async def _load_team_or_404(session: AsyncSession, team_id: uuid.UUID) -> DutyTeam:
    result = await session.execute(
        select(DutyTeam)
        .options(selectinload(DutyTeam.members), selectinload(DutyTeam.duties))
        .where(DutyTeam.id == team_id)
    )
    team = result.scalar_one_or_none()
    if team is None:
        raise HTTPException(status_code=404, detail="DUTY_TEAM_NOT_FOUND")
    return team


async def _build_team_out(session: AsyncSession, team: DutyTeam) -> DutyTeamOut:
    on_date = today()
    period_index = compute_period_index(team, on_date)
    start, end = period_bounds(team, period_index)
    assignments_by_duty = await resolve_all_current_assignments(session, team)

    return DutyTeamOut(
        id=team.id,
        name=team.name,
        description=team.description,
        start_date=team.start_date,
        rotation_interval_days=team.rotation_interval_days,
        created_by_id=team.created_by_id,
        created_at=team.created_at,
        members=list(team.members),
        duties=list(team.duties),
        current_period=TeamPeriodOut(period_index=period_index, start_date=start, end_date=end),
        current_assignments=[
            TeamAssignmentOut(duty_id=duty.id, duty_title=duty.title, assignee_user_id=assignments_by_duty[duty.id])
            for duty in team.duties
            if duty.is_active
        ],
    )


@router.get("", response_model=list[DutyTeamOut])
async def list_duty_teams(session: AsyncSession = Depends(get_session)):
    result = await session.execute(
        select(DutyTeam)
        .options(selectinload(DutyTeam.members), selectinload(DutyTeam.duties))
        .order_by(DutyTeam.name)
    )
    teams = result.scalars().unique().all()
    return [await _build_team_out(session, t) for t in teams]


@router.post("", response_model=DutyTeamOut, status_code=201)
async def create_duty_team(
    data: DutyTeamCreate,
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_session),
):
    team = DutyTeam(
        name=data.name,
        description=data.description,
        start_date=data.start_date,
        rotation_interval_days=data.rotation_interval_days,
        created_by_id=user.id,
    )
    session.add(team)
    await session.flush()

    for index, user_id in enumerate(data.member_user_ids):
        session.add(DutyTeamMember(team_id=team.id, user_id=user_id, order_index=index))
    await session.commit()

    return await _build_team_out(session, await _load_team_or_404(session, team.id))


@router.get("/{team_id}", response_model=DutyTeamOut)
async def get_duty_team(team_id: uuid.UUID, session: AsyncSession = Depends(get_session)):
    team = await _load_team_or_404(session, team_id)
    return await _build_team_out(session, team)


@router.patch("/{team_id}", response_model=DutyTeamOut)
async def update_duty_team(
    team_id: uuid.UUID, data: DutyTeamUpdate, session: AsyncSession = Depends(get_session)
):
    team = await _load_team_or_404(session, team_id)

    if data.name is not None:
        team.name = data.name
    if data.description is not None:
        team.description = data.description
    if data.rotation_interval_days is not None:
        team.rotation_interval_days = data.rotation_interval_days

    if data.member_user_ids is not None:
        await session.execute(delete(DutyTeamMember).where(DutyTeamMember.team_id == team_id))
        await session.flush()
        for index, user_id in enumerate(data.member_user_ids):
            session.add(DutyTeamMember(team_id=team_id, user_id=user_id, order_index=index))
        await session.commit()
        await session.refresh(team, attribute_names=["members"])
    else:
        await session.commit()

    return await _build_team_out(session, team)


@router.delete("/{team_id}", status_code=204)
async def delete_duty_team(team_id: uuid.UUID, session: AsyncSession = Depends(get_session)):
    """Deletes every duty attached to this team too (see the CASCADE comment on
    Duty.team_id) — a team-attached duty has no rotation config of its own to fall back to.
    """
    team = await _load_team_or_404(session, team_id)
    await session.delete(team)
    await session.commit()
