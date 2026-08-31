import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.event import EventType, RSVPStatus


class EventSeriesOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    description: str | None
    created_by_id: uuid.UUID
    created_at: datetime


class EventSeriesCreate(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    description: str | None = None


class EventRSVPOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: uuid.UUID
    status: RSVPStatus
    responded_at: datetime


class EventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    event_type: EventType
    description: str | None
    location: str | None
    start_at: datetime
    end_at: datetime | None
    series_id: uuid.UUID | None
    created_by_id: uuid.UUID
    created_at: datetime
    rsvps: list[EventRSVPOut]


class EventCreate(BaseModel):
    title: str = Field(min_length=1, max_length=150)
    event_type: EventType = EventType.other
    description: str | None = None
    location: str | None = None
    start_at: datetime
    end_at: datetime | None = None
    series_id: uuid.UUID | None = None


class EventUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=150)
    event_type: EventType | None = None
    description: str | None = None
    location: str | None = None
    start_at: datetime | None = None
    end_at: datetime | None = None
    series_id: uuid.UUID | None = None


class RSVPIn(BaseModel):
    status: RSVPStatus
