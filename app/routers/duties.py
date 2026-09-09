import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth.backend import current_active_user
from app.db import get_session
from app.models.duty import Duty, DutyAssignee, DutyOccurrence, DutyOverride
from app.models.user import User
from app.schemas.duty import (
    CurrentPeriodOut,
    DutyCreate,
    DutyDetailOut,
    DutyOccurrenceOut,
    DutyOut,
    DutyOverrideCreate,
    DutyOverrideOut,
    DutyUpdate,
    OccurrenceReassignIn,
    OnDutyTodayOut,
    UpcomingOccurrenceOut,
)
from app.services.absences import is_user_away, load_active_absences_by_user
from app.services.duty_status import build_on_duty_today
from app.services.duty_teams import load_team_with_relations, resolve_team_duty_current_assignee
from app.services.occurrences import DEFAULT_HORIZON_DAYS, ensure_occurrences_materialized
from app.services.rotation import (
    compute_period_index,
    overrides_by_period_index,
    period_bounds,
    resolve_assignee_for_period,
    sorted_assignees,
)
from app.timeutils import today

router = APIRouter(prefix="/api/duties", tags=["duties"], dependencies=[Depends(current_active_user)])


async def _build_current_period(session: AsyncSession, duty: Duty) -> CurrentPeriodOut:
    on_date = today()

    if duty.team_id is not None:
        team = await load_team_with_relations(session, duty.team_id)
        if team is None:
            raise HTTPException(status_code=500, detail="DUTY_TEAM_MISSING")
        period_index = compute_period_index(team, on_date)
        assignee_id = await resolve_team_duty_current_assignee(session, team, duty, on_date)
        start, end = period_bounds(team, period_index)
        return CurrentPeriodOut(
            period_index=period_index, start_date=start, end_date=end, assignee_user_id=assignee_id
        )

    ordered = sorted_assignees(duty.assignees)
    period_index = compute_period_index(duty, on_date)
    overrides_by_period = overrides_by_period_index(duty.overrides)
    assignee_id = resolve_assignee_for_period(ordered, overrides_by_period, period_index)
    start, end = period_bounds(duty, period_index)
    return CurrentPeriodOut(
        period_index=period_index, start_date=start, end_date=end, assignee_user_id=assignee_id
    )


async def _build_duty_out(session: AsyncSession, duty: Duty) -> DutyOut:
    return DutyOut(
        id=duty.id,
        title=duty.title,
        description=duty.description,
        start_date=duty.start_date,
        task_interval_days=duty.task_interval_days,
        rotation_interval_days=duty.rotation_interval_days,
        team_id=duty.team_id,
        is_active=duty.is_active,
        created_by_id=duty.created_by_id,
        created_at=duty.created_at,
        assignees=list(duty.assignees),
        current_period=await _build_current_period(session, duty),
    )


async def _load_duty_or_404(session: AsyncSession, duty_id: uuid.UUID) -> Duty:
    result = await session.execute(
        select(Duty)
        .options(selectinload(Duty.assignees), selectinload(Duty.overrides))
        .where(Duty.id == duty_id)
    )
    duty = result.scalar_one_or_none()
    if duty is None:
        raise HTTPException(status_code=404, detail="DUTY_NOT_FOUND")
    return duty


async def _load_occurrence_or_404(
    session: AsyncSession, duty_id: uuid.UUID, occurrence_id: uuid.UUID
) -> DutyOccurrence:
    result = await session.execute(
        select(DutyOccurrence).where(
            DutyOccurrence.id == occurrence_id, DutyOccurrence.duty_id == duty_id
        )
    )
    occurrence = result.scalar_one_or_none()
    if occurrence is None:
        raise HTTPException(status_code=404, detail="OCCURRENCE_NOT_FOUND")
    return occurrence


def _occurrence_visible_to(occurrence: DutyOccurrence, user: User, assignee_away: bool) -> bool:
    """The assignee, a superuser, or — while the assignee is marked away — any member can see
    this occurrence's completion status and toggle it done. The away exception exists so a
    duty doesn't just silently go undone (or invisibly stuck) while its assignee can't act on
    it; someone else stepping in needs to actually see it to fix it.
    """
    return occurrence.assigned_user_id == user.id or user.is_superuser or assignee_away


async def _build_occurrence_out(
    session: AsyncSession, occurrence: DutyOccurrence, requesting_user: User
) -> DutyOccurrenceOut:
    absences_by_user = await load_active_absences_by_user(session, [occurrence.assigned_user_id])
    away = is_user_away(absences_by_user, occurrence.assigned_user_id, occurrence.due_date)
    visible = _occurrence_visible_to(occurrence, requesting_user, away)
    return DutyOccurrenceOut(
        id=occurrence.id,
        due_date=occurrence.due_date,
        period_index=occurrence.period_index,
        assigned_user_id=occurrence.assigned_user_id,
        is_manual_override=occurrence.is_manual_override,
        is_done=occurrence.is_done if visible else None,
        done_by_id=occurrence.done_by_id if visible else None,
        done_at=occurrence.done_at if visible else None,
        assignee_away=away,
    )


@router.get("", response_model=list[DutyOut])
async def list_duties(session: AsyncSession = Depends(get_session)):
    result = await session.execute(
        select(Duty)
        .options(selectinload(Duty.assignees), selectinload(Duty.overrides))
        .where(Duty.is_active.is_(True))
        .order_by(Duty.title)
    )
    duties = result.scalars().unique().all()
    return [await _build_duty_out(session, d) for d in duties]


@router.get("/on-duty-today", response_model=list[OnDutyTodayOut])
async def on_duty_today(
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_session),
):
    entries = await build_on_duty_today(session, today())
    on_date = today()

    absences_by_user = await load_active_absences_by_user(
        session, list({e["assignee_user_id"] for e in entries})
    )

    # Resolve today's occurrence for the caller's own entries, for a superuser, or for any
    # entry whose assignee is currently away — that's what lets Home's "Your duties" widget
    # check something off without navigating to the duty detail page, and lets someone else
    # step in for an away member, without leaking anyone else's completion status.
    resolvable_duty_ids = [
        e["duty_id"]
        for e in entries
        if e["assignee_user_id"] == user.id
        or user.is_superuser
        or is_user_away(absences_by_user, e["assignee_user_id"], on_date)
    ]
    occurrence_by_duty_id: dict[uuid.UUID, DutyOccurrence] = {}
    if resolvable_duty_ids:
        duties_result = await session.execute(select(Duty).where(Duty.id.in_(resolvable_duty_ids)))
        for duty in duties_result.scalars():
            await ensure_occurrences_materialized(session, duty, on_date)

        occ_result = await session.execute(
            select(DutyOccurrence)
            .where(DutyOccurrence.duty_id.in_(resolvable_duty_ids), DutyOccurrence.due_date <= on_date)
            .order_by(DutyOccurrence.due_date.desc())
        )
        for occurrence in occ_result.scalars():
            # Order by due_date desc means the first row seen per duty is the most recent.
            occurrence_by_duty_id.setdefault(occurrence.duty_id, occurrence)

    out = []
    for entry in entries:
        occurrence = occurrence_by_duty_id.get(entry["duty_id"])
        out.append(
            OnDutyTodayOut(
                duty_id=entry["duty_id"],
                duty_title=entry["duty_title"],
                assignee_user_id=entry["assignee_user_id"],
                occurrence_id=occurrence.id if occurrence else None,
                is_done=occurrence.is_done if occurrence else None,
            )
        )
    return out


@router.get("/occurrences/upcoming", response_model=list[UpcomingOccurrenceOut])
async def upcoming_occurrences(
    horizon_days: int = Query(DEFAULT_HORIZON_DAYS, gt=0, le=730),
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_session),
):
    """Flat, cross-duty feed for the combined calendar view — materializes every active
    duty's occurrences up to `horizon_days` out (defaulting to the same rolling horizon the
    per-duty detail view uses). The calendar's month/week grid passes a larger value when
    the visible range extends further out than that default.
    """
    result = await session.execute(
        select(Duty)
        .options(selectinload(Duty.assignees), selectinload(Duty.overrides))
        .where(Duty.is_active.is_(True))
    )
    duties = result.scalars().unique().all()

    horizon = today() + timedelta(days=horizon_days)
    for duty in duties:
        await ensure_occurrences_materialized(session, duty, horizon)

    duty_by_id = {d.id: d for d in duties}
    if not duty_by_id:
        return []

    occ_result = await session.execute(
        select(DutyOccurrence)
        .where(DutyOccurrence.duty_id.in_(duty_by_id.keys()))
        .order_by(DutyOccurrence.due_date)
    )
    occurrences = list(occ_result.scalars())
    absences_by_user = await load_active_absences_by_user(
        session, list({o.assigned_user_id for o in occurrences})
    )
    return [
        UpcomingOccurrenceOut(
            duty_id=o.duty_id,
            duty_title=duty_by_id[o.duty_id].title,
            due_date=o.due_date,
            assigned_user_id=o.assigned_user_id,
            is_done=(
                o.is_done
                if _occurrence_visible_to(
                    o, user, is_user_away(absences_by_user, o.assigned_user_id, o.due_date)
                )
                else None
            ),
        )
        for o in occurrences
    ]


@router.post("", response_model=DutyOut, status_code=201)
async def create_duty(
    data: DutyCreate,
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_session),
):
    duty = Duty(
        title=data.title,
        description=data.description,
        start_date=data.start_date,
        task_interval_days=data.task_interval_days,
        rotation_interval_days=data.rotation_interval_days,
        team_id=data.team_id,
        created_by_id=user.id,
    )
    session.add(duty)
    await session.flush()

    for index, user_id in enumerate(data.assignee_user_ids):
        session.add(DutyAssignee(duty_id=duty.id, user_id=user_id, order_index=index))
    await session.commit()

    return await _build_duty_out(session, await _load_duty_or_404(session, duty.id))


@router.get("/{duty_id}", response_model=DutyDetailOut)
async def get_duty(
    duty_id: uuid.UUID,
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_session),
):
    duty = await _load_duty_or_404(session, duty_id)
    horizon = today() + timedelta(days=DEFAULT_HORIZON_DAYS)
    await ensure_occurrences_materialized(session, duty, horizon)

    occ_result = await session.execute(
        select(DutyOccurrence).where(DutyOccurrence.duty_id == duty_id).order_by(DutyOccurrence.due_date)
    )
    occurrences = list(occ_result.scalars())

    occurrence_outs = [await _build_occurrence_out(session, o, user) for o in occurrences]

    base = await _build_duty_out(session, duty)
    return DutyDetailOut(
        **base.model_dump(),
        occurrences=occurrence_outs,
        overrides=list(duty.overrides),
    )


@router.patch("/{duty_id}", response_model=DutyOut)
async def update_duty(
    duty_id: uuid.UUID, data: DutyUpdate, session: AsyncSession = Depends(get_session)
):
    duty = await _load_duty_or_404(session, duty_id)

    if data.title is not None:
        duty.title = data.title
    if data.description is not None:
        duty.description = data.description
    if data.is_active is not None:
        duty.is_active = data.is_active
    if data.task_interval_days is not None:
        duty.task_interval_days = data.task_interval_days
    if data.rotation_interval_days is not None:
        duty.rotation_interval_days = data.rotation_interval_days

    if data.team_id is not None:
        # Attaching to a team makes the duty's own rotation_interval_days/assignees
        # meaningless — clear them so a leftover manual config can't confuse anyone (the
        # schema already rejects setting team_id together with either field in this same
        # request, but this covers a duty that already had them from before).
        duty.team_id = data.team_id
        duty.rotation_interval_days = None
        await session.execute(delete(DutyAssignee).where(DutyAssignee.duty_id == duty_id))
        await session.flush()
        await session.commit()
        await session.refresh(duty, attribute_names=["assignees"])
    elif data.assignee_user_ids is not None:
        # Reordering/replacing assignees only affects future materialization — it never
        # rewrites already-snapshotted DutyOccurrence rows.
        await session.execute(delete(DutyAssignee).where(DutyAssignee.duty_id == duty_id))
        await session.flush()
        for index, user_id in enumerate(data.assignee_user_ids):
            session.add(DutyAssignee(duty_id=duty_id, user_id=user_id, order_index=index))
        await session.commit()
        # `duty` was loaded (with assignees) at the top of this request and is still the
        # same object the session's identity map will hand back on any further query in
        # this session — a raw bulk delete()/add() doesn't refresh an already-loaded
        # relationship collection on its own, so re-querying here would silently return
        # the pre-update assignee list instead of the one just written.
        await session.refresh(duty, attribute_names=["assignees"])
    else:
        await session.commit()

    return await _build_duty_out(session, duty)


@router.delete("/{duty_id}", status_code=204)
async def delete_duty(duty_id: uuid.UUID, session: AsyncSession = Depends(get_session)):
    duty = await _load_duty_or_404(session, duty_id)
    await session.delete(duty)
    await session.commit()


@router.post("/{duty_id}/occurrences/{occurrence_id}/toggle-done", response_model=DutyOccurrenceOut)
async def toggle_occurrence_done(
    duty_id: uuid.UUID,
    occurrence_id: uuid.UUID,
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_session),
):
    occurrence = await _load_occurrence_or_404(session, duty_id, occurrence_id)
    absences_by_user = await load_active_absences_by_user(session, [occurrence.assigned_user_id])
    away = is_user_away(absences_by_user, occurrence.assigned_user_id, occurrence.due_date)
    if not _occurrence_visible_to(occurrence, user, away):
        raise HTTPException(status_code=403, detail="NOT_YOUR_OCCURRENCE")
    occurrence.is_done = not occurrence.is_done
    occurrence.done_by_id = user.id if occurrence.is_done else None
    occurrence.done_at = datetime.now(timezone.utc) if occurrence.is_done else None
    await session.commit()
    return await _build_occurrence_out(session, occurrence, user)


@router.patch("/{duty_id}/occurrences/{occurrence_id}", response_model=DutyOccurrenceOut)
async def reassign_occurrence(
    duty_id: uuid.UUID,
    occurrence_id: uuid.UUID,
    data: OccurrenceReassignIn,
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_session),
):
    """Swap a single already-materialized occurrence. For a future period that has no
    occurrences yet, create a DutyOverride instead (POST .../overrides) — that's what
    materialization consults when generating new rows. Reassignment (who's responsible) is
    deliberately left open to any member, unlike the completion status itself — see
    _can_see_occurrence_status/toggle_occurrence_done.
    """
    occurrence = await _load_occurrence_or_404(session, duty_id, occurrence_id)
    occurrence.assigned_user_id = data.assigned_user_id
    occurrence.is_manual_override = True
    await session.commit()
    return await _build_occurrence_out(session, occurrence, user)


@router.post("/{duty_id}/overrides", response_model=DutyOverrideOut, status_code=201)
async def upsert_override(
    duty_id: uuid.UUID,
    data: DutyOverrideCreate,
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_session),
):
    await _load_duty_or_404(session, duty_id)

    result = await session.execute(
        select(DutyOverride).where(
            DutyOverride.duty_id == duty_id, DutyOverride.period_index == data.period_index
        )
    )
    override = result.scalar_one_or_none()
    if override is None:
        override = DutyOverride(
            duty_id=duty_id,
            period_index=data.period_index,
            assignee_user_id=data.assignee_user_id,
            reason=data.reason,
            created_by_id=user.id,
        )
        session.add(override)
    else:
        override.assignee_user_id = data.assignee_user_id
        override.reason = data.reason

    await session.commit()
    await session.refresh(override)
    return override


@router.delete("/{duty_id}/overrides/{override_id}", status_code=204)
async def delete_override(
    duty_id: uuid.UUID, override_id: uuid.UUID, session: AsyncSession = Depends(get_session)
):
    result = await session.execute(
        select(DutyOverride).where(DutyOverride.id == override_id, DutyOverride.duty_id == duty_id)
    )
    override = result.scalar_one_or_none()
    if override is None:
        raise HTTPException(status_code=404, detail="OVERRIDE_NOT_FOUND")
    await session.delete(override)
    await session.commit()
