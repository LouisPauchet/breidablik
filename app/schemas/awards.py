import uuid
from datetime import date, datetime

from pydantic import BaseModel, Field


class AwardVoteTallyOut(BaseModel):
    candidate_user_id: uuid.UUID
    vote_count: int


class AwardCycleOut(BaseModel):
    id: uuid.UUID
    month: date
    phase: str
    drawn_category_title: str | None
    drawn_category_emoji: str | None
    drawn_category_suggested_by_id: uuid.UUID | None
    duty_master_winner_id: uuid.UUID | None
    duty_master_win_count: int | None
    community_award_winner_id: uuid.UUID | None
    community_award_vote_count: int | None
    community_award_vetoed: bool
    finalized_at: datetime | None


class AwardCurrentStateOut(AwardCycleOut):
    my_suggestion_submitted: bool
    my_vote_candidate_id: uuid.UUID | None
    votes: list[AwardVoteTallyOut]


class AwardSummaryOut(BaseModel):
    current: AwardCurrentStateOut | None
    latest_decided: AwardCycleOut | None


class AwardSuggestionCreate(BaseModel):
    title: str = Field(min_length=1, max_length=100)
    emoji: str = Field(min_length=1, max_length=32)


class AwardVoteIn(BaseModel):
    candidate_user_id: uuid.UUID


class AwardVetoIn(BaseModel):
    reason: str | None = Field(default=None, max_length=255)


class AwardTickIn(BaseModel):
    as_of: date | None = None


class MemberAwardBadgeOut(BaseModel):
    month: date
    kind: str
    title: str | None
    emoji: str | None


class MemberAwardHistoryOut(BaseModel):
    user_id: uuid.UUID
    badges: list[MemberAwardBadgeOut]
