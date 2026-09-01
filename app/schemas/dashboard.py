import uuid
from datetime import datetime

from pydantic import BaseModel


class DashboardTokenOut(BaseModel):
    token: str


class DashboardQuoteOut(BaseModel):
    text: str
    author: str


class DashboardOnDutyOut(BaseModel):
    duty_id: uuid.UUID
    duty_title: str
    assignee_user_id: uuid.UUID
    assignee_display_name: str
    assignee_avatar_updated_at: datetime | None


class DashboardAgendaEntryOut(BaseModel):
    key: str
    kind: str
    title: str
    detail: str
    at: datetime


class DashboardActivityEntryOut(BaseModel):
    at: datetime
    text: str


class DashboardOut(BaseModel):
    generated_at: datetime
    quote: DashboardQuoteOut
    on_duty_today: list[DashboardOnDutyOut]
    upcoming: list[DashboardAgendaEntryOut]
    activity: list[DashboardActivityEntryOut]
