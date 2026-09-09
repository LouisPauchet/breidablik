import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ContestDutyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    description: str | None
    icon: str
    min_interval_minutes: int
    show_on_home: bool
    is_active: bool
    created_by_id: uuid.UUID
    created_at: datetime


class ContestSummaryEntryOut(ContestDutyOut):
    # Only ever the requesting user's own count — see
    # app/services/contests.py:get_my_month_counts for why nobody sees anyone else's.
    my_count: int
    next_log_allowed_at: datetime | None


class ContestDutyCreate(BaseModel):
    title: str = Field(min_length=1, max_length=150)
    description: str | None = None
    icon: str = Field(min_length=1, max_length=32)
    min_interval_minutes: int = Field(default=0, ge=0)
    show_on_home: bool = False


class ContestDutyUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=150)
    description: str | None = None
    icon: str | None = Field(default=None, min_length=1, max_length=32)
    min_interval_minutes: int | None = Field(default=None, ge=0)
    show_on_home: bool | None = None
    is_active: bool | None = None


class ContestLogEntryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    contest_duty_id: uuid.UUID
    user_id: uuid.UUID
    logged_at: datetime
