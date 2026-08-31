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
    created_at: datetime


class AbsenceCreate(BaseModel):
    start_date: date
    end_date: date
    reason: str | None = None

    @model_validator(mode="after")
    def check_date_order(self) -> "AbsenceCreate":
        if self.end_date < self.start_date:
            raise ValueError("end_date must not be before start_date")
        return self
