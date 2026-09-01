import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth.backend import current_active_user
from app.db import get_session
from app.models.event import Event, EventRSVP, EventSeries
from app.models.user import User
from app.schemas.event import (
    EventCreate,
    EventOut,
    EventSeriesCreate,
    EventSeriesOut,
    EventUpdate,
    RSVPIn,
)
from app.services.notifications import notify_event_created

router = APIRouter(prefix="/api/events", tags=["events"], dependencies=[Depends(current_active_user)])


async def _load_event_or_404(session: AsyncSession, event_id: uuid.UUID) -> Event:
    result = await session.execute(
        select(Event).options(selectinload(Event.rsvps)).where(Event.id == event_id)
    )
    event = result.scalar_one_or_none()
    if event is None:
        raise HTTPException(status_code=404, detail="EVENT_NOT_FOUND")
    return event


@router.get("/series", response_model=list[EventSeriesOut])
async def list_series(session: AsyncSession = Depends(get_session)):
    result = await session.execute(select(EventSeries).order_by(EventSeries.name))
    return list(result.scalars())


@router.post("/series", response_model=EventSeriesOut, status_code=201)
async def create_series(
    data: EventSeriesCreate,
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_session),
):
    series = EventSeries(name=data.name, description=data.description, created_by_id=user.id)
    session.add(series)
    await session.commit()
    await session.refresh(series)
    return series


@router.get("", response_model=list[EventOut])
async def list_events(
    series_id: uuid.UUID | None = None, session: AsyncSession = Depends(get_session)
):
    query = select(Event).options(selectinload(Event.rsvps)).order_by(Event.start_at)
    if series_id is not None:
        query = query.where(Event.series_id == series_id)
    result = await session.execute(query)
    return list(result.scalars().unique())


@router.post("", response_model=EventOut, status_code=201)
async def create_event(
    data: EventCreate,
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_session),
):
    event = Event(
        title=data.title,
        event_type=data.event_type,
        description=data.description,
        location=data.location,
        start_at=data.start_at,
        end_at=data.end_at,
        series_id=data.series_id,
        created_by_id=user.id,
    )
    session.add(event)
    await session.commit()
    event = await _load_event_or_404(session, event.id)
    await notify_event_created(session, event, user)
    return event


@router.get("/{event_id}", response_model=EventOut)
async def get_event(event_id: uuid.UUID, session: AsyncSession = Depends(get_session)):
    return await _load_event_or_404(session, event_id)


@router.patch("/{event_id}", response_model=EventOut)
async def update_event(
    event_id: uuid.UUID, data: EventUpdate, session: AsyncSession = Depends(get_session)
):
    event = await _load_event_or_404(session, event_id)

    if data.title is not None:
        event.title = data.title
    if data.event_type is not None:
        event.event_type = data.event_type
    if data.description is not None:
        event.description = data.description
    if data.location is not None:
        event.location = data.location
    if data.start_at is not None:
        event.start_at = data.start_at
    if data.end_at is not None:
        event.end_at = data.end_at
    if data.series_id is not None:
        event.series_id = data.series_id

    await session.commit()
    return await _load_event_or_404(session, event_id)


@router.delete("/{event_id}", status_code=204)
async def delete_event(event_id: uuid.UUID, session: AsyncSession = Depends(get_session)):
    event = await _load_event_or_404(session, event_id)
    await session.delete(event)
    await session.commit()


@router.put("/{event_id}/rsvp", response_model=EventOut)
async def upsert_rsvp(
    event_id: uuid.UUID,
    data: RSVPIn,
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_session),
):
    await _load_event_or_404(session, event_id)

    result = await session.execute(
        select(EventRSVP).where(EventRSVP.event_id == event_id, EventRSVP.user_id == user.id)
    )
    rsvp = result.scalar_one_or_none()
    if rsvp is None:
        session.add(EventRSVP(event_id=event_id, user_id=user.id, status=data.status))
    else:
        rsvp.status = data.status
        rsvp.responded_at = datetime.now(timezone.utc)

    await session.commit()
    return await _load_event_or_404(session, event_id)
