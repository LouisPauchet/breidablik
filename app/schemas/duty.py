import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field


class DutyAssigneeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: uuid.UUID
    order_index: int


class CurrentPeriodOut(BaseModel):
    period_index: int
    start_date: date
    end_date: date
    assignee_user_id: uuid.UUID


class DutyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    description: str | None
    start_date: date
    task_interval_days: int
    rotation_interval_days: int
    is_active: bool
    created_by_id: uuid.UUID
    created_at: datetime
    assignees: list[DutyAssigneeOut]
    current_period: CurrentPeriodOut


class DutyOccurrenceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    due_date: date
    period_index: int
    assigned_user_id: uuid.UUID
    is_manual_override: bool
    is_done: bool
    done_by_id: uuid.UUID | None
    done_at: datetime | None


class DutyOverrideOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    period_index: int
    assignee_user_id: uuid.UUID
    reason: str | None
    created_by_id: uuid.UUID
    created_at: datetime


class DutyDetailOut(DutyOut):
    occurrences: list[DutyOccurrenceOut]
    overrides: list[DutyOverrideOut]


class DutyCreate(BaseModel):
    title: str = Field(min_length=1, max_length=150)
    description: str | None = None
    start_date: date
    task_interval_days: int = Field(gt=0)
    rotation_interval_days: int = Field(gt=0)
    assignee_user_ids: list[uuid.UUID] = Field(min_length=1)


class DutyUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=150)
    description: str | None = None
    is_active: bool | None = None
    task_interval_days: int | None = Field(default=None, gt=0)
    rotation_interval_days: int | None = Field(default=None, gt=0)
    assignee_user_ids: list[uuid.UUID] | None = Field(default=None, min_length=1)


class OccurrenceReassignIn(BaseModel):
    assigned_user_id: uuid.UUID


class DutyOverrideCreate(BaseModel):
    period_index: int
    assignee_user_id: uuid.UUID
    reason: str | None = None


class OnDutyTodayOut(BaseModel):
    duty_id: uuid.UUID
    duty_title: str
    assignee_user_id: uuid.UUID
