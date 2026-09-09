import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, Integer, String, Text, UniqueConstraint, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class ContestDuty(Base):
    """An open, unscheduled, unassigned chore anyone can do and log whenever they do it (e.g.
    "empty the dishwasher") — deliberately separate from Duty/DutyOccurrence, which always
    resolve to exactly one assignee per scheduled occurrence via rotation or a team chore-wheel.
    A contest duty has neither a schedule nor an assignee; ContestLogEntry is an append-only
    record of who did it and when, tallied monthly for a "best performer" award (see
    app/services/awards.py's finalize step and ContestAwardResult below).

    No delete endpoint is exposed for this model (see app/routers/contests.py) — a past
    ContestAwardResult joins back to this row for its title/icon rather than snapshotting them,
    so hard-deleting a contest duty would corrupt earlier award-history badges. Archive via
    is_active instead, same as Duty.
    """

    __tablename__ = "contest_duty"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(String(150))
    description: Mapped[str | None] = mapped_column(Text, default=None)
    icon: Mapped[str] = mapped_column(String(32))
    is_active: Mapped[bool] = mapped_column(default=True)
    created_by_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("user.id"))
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    log_entries: Mapped[list["ContestLogEntry"]] = relationship(
        back_populates="contest_duty", cascade="all, delete-orphan"
    )


class ContestLogEntry(Base):
    """One self-logged completion. Multiple entries per user per month are expected and
    counted — this is a tally, not a toggle.
    """

    __tablename__ = "contest_log_entry"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    contest_duty_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("contest_duty.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("user.id"))
    logged_at: Mapped[datetime] = mapped_column(server_default=func.now())

    contest_duty: Mapped["ContestDuty"] = relationship(back_populates="log_entries")


class ContestAwardResult(Base):
    """One row per (award cycle, active contest duty) at month-end finalization — see
    app/services/awards.py:_finalize_cycle. Never vetoable, unlike the community award: a
    contest result is an objective count of a visible, self-logged action, not a subjective
    member-suggested category.
    """

    __tablename__ = "contest_award_result"
    __table_args__ = (
        UniqueConstraint("cycle_id", "contest_duty_id", name="uq_contest_award_result_cycle_duty"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    cycle_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("award_cycle.id", ondelete="CASCADE"), index=True)
    contest_duty_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("contest_duty.id", ondelete="CASCADE"))
    winner_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("user.id"), default=None)
    completion_count: Mapped[int | None] = mapped_column(Integer, default=None)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    contest_duty: Mapped["ContestDuty"] = relationship()
