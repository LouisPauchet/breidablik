import enum
import uuid
from datetime import date, datetime

from sqlalchemy import Boolean, Date, Enum, ForeignKey, Integer, String, UniqueConstraint, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class AwardCyclePhase(str, enum.Enum):
    suggesting = "suggesting"
    voting = "voting"
    decided = "decided"


class AwardCycle(Base):
    """One row per calendar month (`month` is always that month's 1st). Drives the state
    machine for both awards that month — see app/services/awards.py:run_award_cycle_tick.
    Both awards' results are persisted here once finalized rather than recomputed on every
    page view, since the member award-history page and Avatar badges need to read them
    cheaply and often.
    """

    __tablename__ = "award_cycle"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    month: Mapped[date] = mapped_column(Date, unique=True, index=True)
    phase: Mapped[AwardCyclePhase] = mapped_column(
        Enum(AwardCyclePhase, name="awardcyclephase"), default=AwardCyclePhase.suggesting
    )

    # Idempotency guards for the periodic tick, same role as DutyOccurrence.reminder_sent_at.
    suggestion_window_opened_at: Mapped[datetime | None] = mapped_column(default=None)
    voting_window_opened_at: Mapped[datetime | None] = mapped_column(default=None)
    finalized_at: Mapped[datetime | None] = mapped_column(default=None)

    drawn_suggestion_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("award_category_suggestion.id"), default=None
    )

    duty_master_winner_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("user.id"), default=None)
    duty_master_win_count: Mapped[int | None] = mapped_column(Integer, default=None)

    community_award_winner_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("user.id"), default=None)
    community_award_vote_count: Mapped[int | None] = mapped_column(Integer, default=None)
    community_award_vetoed: Mapped[bool] = mapped_column(Boolean, default=False)
    community_award_veto_by_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("user.id"), default=None)
    community_award_veto_at: Mapped[datetime | None] = mapped_column(default=None)
    community_award_veto_reason: Mapped[str | None] = mapped_column(String(255), default=None)

    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    # Two FK paths exist between award_cycle and award_category_suggestion (a cycle's own
    # suggestions, and the one drawn from among them) — foreign_keys must be given explicitly
    # on both relationships or SQLAlchemy raises AmbiguousForeignKeysError at mapper-config time.
    suggestions: Mapped[list["AwardCategorySuggestion"]] = relationship(
        back_populates="cycle",
        foreign_keys="AwardCategorySuggestion.cycle_id",
        cascade="all, delete-orphan",
    )
    drawn_suggestion: Mapped["AwardCategorySuggestion | None"] = relationship(
        foreign_keys=[drawn_suggestion_id]
    )


class AwardCategorySuggestion(Base):
    """A member-proposed award category (title + emoji) for one cycle. One per member per
    cycle — see the unique constraint below — so the weighted draw stays meaningful.
    """

    __tablename__ = "award_category_suggestion"
    __table_args__ = (
        UniqueConstraint("cycle_id", "suggested_by_id", name="uq_award_suggestion_member_per_cycle"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    cycle_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("award_cycle.id", ondelete="CASCADE"), index=True
    )
    title: Mapped[str] = mapped_column(String(100))
    emoji: Mapped[str] = mapped_column(String(32))
    suggested_by_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("user.id"))
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    cycle: Mapped["AwardCycle"] = relationship(back_populates="suggestions", foreign_keys=[cycle_id])


class AwardCategoryVote(Base):
    """One vote per (cycle, voter) — upsert pattern identical to EventRSVP."""

    __tablename__ = "award_category_vote"
    __table_args__ = (UniqueConstraint("cycle_id", "voter_id", name="uq_award_vote_one_per_voter_per_cycle"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    cycle_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("award_cycle.id", ondelete="CASCADE"), index=True)
    voter_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("user.id"))
    candidate_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("user.id"), index=True)
    voted_at: Mapped[datetime] = mapped_column(server_default=func.now())
