import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ContestDutyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    description: str | None
    icon: str
    is_active: bool
    created_by_id: uuid.UUID
    created_at: datetime


class ContestTallyEntryOut(BaseModel):
    user_id: uuid.UUID
    count: int


class ContestSummaryEntryOut(ContestDutyOut):
    tally: list[ContestTallyEntryOut]


class ContestDutyCreate(BaseModel):
    title: str = Field(min_length=1, max_length=150)
    description: str | None = None
    icon: str = Field(min_length=1, max_length=32)


class ContestDutyUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=150)
    description: str | None = None
    icon: str | None = Field(default=None, min_length=1, max_length=32)
    is_active: bool | None = None


class ContestLogEntryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    contest_duty_id: uuid.UUID
    user_id: uuid.UUID
    logged_at: datetime
