import uuid
from datetime import date, datetime

from sqlalchemy import Date, ForeignKey, Integer, String, Text, UniqueConstraint, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class Duty(Base):
    """A recurring chore with two independent cadences: how often it needs doing
    (task_interval_days) and how often the responsible person changes
    (rotation_interval_days) — e.g. bathroom cleaned weekly, responsibility rotates every
    two weeks. Both are anchored to the same start_date.
    """

    __tablename__ = "duty"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(String(150))
    description: Mapped[str | None] = mapped_column(Text, default=None)

    start_date: Mapped[date] = mapped_column(Date)
    task_interval_days: Mapped[int] = mapped_column(Integer)
    rotation_interval_days: Mapped[int] = mapped_column(Integer)

    is_active: Mapped[bool] = mapped_column(default=True)
    created_by_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("user.id"))
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    assignees: Mapped[list["DutyAssignee"]] = relationship(
        back_populates="duty", cascade="all, delete-orphan", order_by="DutyAssignee.order_index"
    )
    overrides: Mapped[list["DutyOverride"]] = relationship(
        back_populates="duty", cascade="all, delete-orphan"
    )
    occurrences: Mapped[list["DutyOccurrence"]] = relationship(
        back_populates="duty", cascade="all, delete-orphan"
    )


class DutyAssignee(Base):
    """Rotation order for a duty. Reordering only affects future materialization — it never
    rewrites already-snapshotted DutyOccurrence rows.
    """

    __tablename__ = "duty_assignee"
    __table_args__ = (
        UniqueConstraint("duty_id", "order_index", name="uq_duty_assignee_order"),
        UniqueConstraint("duty_id", "user_id", name="uq_duty_assignee_user"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    duty_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("duty.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("user.id", ondelete="CASCADE"))
    order_index: Mapped[int] = mapped_column(Integer)

    duty: Mapped["Duty"] = relationship(back_populates="assignees")


class DutyOverride(Base):
    """A pre-planned swap for a whole rotation period (identified by period_index), usable
    even before any DutyOccurrence in that period has been materialized.
    """

    __tablename__ = "duty_override"
    __table_args__ = (UniqueConstraint("duty_id", "period_index", name="uq_duty_override_period"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    duty_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("duty.id", ondelete="CASCADE"), index=True)
    period_index: Mapped[int] = mapped_column(Integer)
    assignee_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("user.id"))
    reason: Mapped[str | None] = mapped_column(String(255), default=None)
    created_by_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("user.id"))
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    duty: Mapped["Duty"] = relationship(back_populates="overrides")


class DutyOccurrence(Base):
    """A single due date for a duty, lazily materialized (see app/services/occurrences.py)
    with the resolved assignee snapshotted at creation time. is_manual_override marks a row
    hand-edited after materialization (e.g. a one-off swap), so it's never mistaken for the
    formula's output.
    """

    __tablename__ = "duty_occurrence"
    __table_args__ = (UniqueConstraint("duty_id", "due_date", name="uq_duty_occurrence_date"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    duty_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("duty.id", ondelete="CASCADE"), index=True)
    due_date: Mapped[date] = mapped_column(Date, index=True)
    period_index: Mapped[int] = mapped_column(Integer)
    assigned_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("user.id"))

    is_manual_override: Mapped[bool] = mapped_column(default=False)
    is_done: Mapped[bool] = mapped_column(default=False)
    done_by_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("user.id"), default=None)
    done_at: Mapped[datetime | None] = mapped_column(default=None)
    reminder_sent_at: Mapped[datetime | None] = mapped_column(default=None)

    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    duty: Mapped["Duty"] = relationship(back_populates="occurrences")
