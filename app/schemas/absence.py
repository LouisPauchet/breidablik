import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, model_validator


class AbsenceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    start_date: date
    end_date: date
    reason: str | None
    auto_reassign: bool
    created_at: datetime


class AbsenceCreate(BaseModel):
    start_date: date
    end_date: date
    reason: str | None = None
    auto_reassign: bool = False

    @model_validator(mode="after")
    def check_date_order(self) -> "AbsenceCreate":
        if self.end_date < self.start_date:
            raise ValueError("end_date must not be before start_date")
        return self


class AbsenceUpdate(BaseModel):
    start_date: date | None = None
    end_date: date | None = None
    reason: str | None = None
    auto_reassign: bool | None = None
