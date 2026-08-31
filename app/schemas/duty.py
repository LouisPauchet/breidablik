import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator


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
    rotation_interval_days: int | None
    team_id: uuid.UUID | None
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
    # Not an ORM column — every route builds this from the Absence table (see
    # app/routers/duties.py:_build_occurrence_out), never from raw attribute access.
    assignee_away: bool


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
    # Exactly one of (team_id) or (rotation_interval_days + assignee_user_ids) must be given —
    # a team-attached duty inherits its rotation entirely from the team's chore-wheel.
    team_id: uuid.UUID | None = None
    rotation_interval_days: int | None = Field(default=None, gt=0)
    assignee_user_ids: list[uuid.UUID] = Field(default_factory=list)

    @model_validator(mode="after")
    def check_team_or_manual_rotation(self) -> "DutyCreate":
        if self.team_id is None:
            if self.rotation_interval_days is None:
                raise ValueError("rotation_interval_days is required for a duty with no team")
            if not self.assignee_user_ids:
                raise ValueError("assignee_user_ids is required for a duty with no team")
        return self


class DutyUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=150)
    description: str | None = None
    is_active: bool | None = None
    task_interval_days: int | None = Field(default=None, gt=0)
    rotation_interval_days: int | None = Field(default=None, gt=0)
    assignee_user_ids: list[uuid.UUID] | None = Field(default=None, min_length=1)
    # Attaches the duty to a team (its own rotation_interval_days/assignees stop being used).
    # There's no way to detach back to manual rotation via update yet — recreate the duty
    # instead if you need that.
    team_id: uuid.UUID | None = None

    @model_validator(mode="after")
    def check_team_not_combined_with_manual_rotation(self) -> "DutyUpdate":
        if self.team_id is not None and (
            self.rotation_interval_days is not None or self.assignee_user_ids is not None
        ):
            raise ValueError("can't set team_id together with rotation_interval_days or assignee_user_ids")
        return self


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


class UpcomingOccurrenceOut(BaseModel):
    duty_id: uuid.UUID
    duty_title: str
    due_date: date
    assigned_user_id: uuid.UUID
    is_done: bool


class DutyTeamMemberOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: uuid.UUID
    order_index: int


class DutyTeamDutySummaryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    is_active: bool


class TeamPeriodOut(BaseModel):
    period_index: int
    start_date: date
    end_date: date


class TeamAssignmentOut(BaseModel):
    duty_id: uuid.UUID
    duty_title: str
    assignee_user_id: uuid.UUID


class DutyTeamOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    description: str | None
    start_date: date
    rotation_interval_days: int
    created_by_id: uuid.UUID
    created_at: datetime
    members: list[DutyTeamMemberOut]
    duties: list[DutyTeamDutySummaryOut]
    current_period: TeamPeriodOut
    current_assignments: list[TeamAssignmentOut]


class DutyTeamCreate(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    description: str | None = None
    start_date: date
    rotation_interval_days: int = Field(gt=0)
    member_user_ids: list[uuid.UUID] = Field(min_length=1)


class DutyTeamUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=150)
    description: str | None = None
    rotation_interval_days: int | None = Field(default=None, gt=0)
    member_user_ids: list[uuid.UUID] | None = Field(default=None, min_length=1)
