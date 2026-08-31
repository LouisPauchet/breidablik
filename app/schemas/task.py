import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field


class TaskOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    description: str | None
    due_date: date | None
    is_done: bool
    done_by_id: uuid.UUID | None
    done_at: datetime | None
    created_by_id: uuid.UUID
    created_at: datetime
    assignee_user_ids: list[uuid.UUID]


class TaskCreate(BaseModel):
    title: str = Field(min_length=1, max_length=150)
    description: str | None = None
    due_date: date | None = None
    assignee_user_ids: list[uuid.UUID] = Field(min_length=1)


class TaskUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=150)
    description: str | None = None
    due_date: date | None = None
    assignee_user_ids: list[uuid.UUID] | None = Field(default=None, min_length=1)
