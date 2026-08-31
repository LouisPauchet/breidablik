import uuid
from datetime import date, datetime

from sqlalchemy import Date, ForeignKey, Integer, String, Text, UniqueConstraint, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class DutyTeam(Base):
    """A group of duties whose responsibility rotates together across a shared set of
    members — a "chore wheel": each rotation period, every attached duty goes to a
    different member, and it's a different assignment again next period (see
    app/services/rotation.py:resolve_team_duty_assignee). start_date anchors the rotation
    the same way Duty.start_date does — pick a date that's already the intended "change
    day" (e.g. a Monday) and, as long as rotation_interval_days is a multiple of 7, every
    later period boundary lands on that same weekday automatically.
    """

    __tablename__ = "duty_team"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(150))
    description: Mapped[str | None] = mapped_column(Text, default=None)

    start_date: Mapped[date] = mapped_column(Date)
    rotation_interval_days: Mapped[int] = mapped_column(Integer)

    created_by_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("user.id"))
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    members: Mapped[list["DutyTeamMember"]] = relationship(
        back_populates="team", cascade="all, delete-orphan", order_by="DutyTeamMember.order_index"
    )
    # cascade="all, delete-orphan" (not just the FK's ondelete="CASCADE") because without it
    # SQLAlchemy's own unit-of-work nulls out Duty.team_id on delete before the DB constraint
    # ever runs, leaving an unresolvable duty (no team, no rotation_interval_days/assignees
    # of its own either) instead of actually deleting it.
    duties: Mapped[list["Duty"]] = relationship(
        back_populates="team", cascade="all, delete-orphan", order_by="Duty.created_at"
    )


class DutyTeamMember(Base):
    __tablename__ = "duty_team_member"
    __table_args__ = (
        UniqueConstraint("team_id", "order_index", name="uq_duty_team_member_order"),
        UniqueConstraint("team_id", "user_id", name="uq_duty_team_member_user"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    team_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("duty_team.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("user.id", ondelete="CASCADE"))
    order_index: Mapped[int] = mapped_column(Integer)

    team: Mapped["DutyTeam"] = relationship(back_populates="members")


class Duty(Base):
    """A recurring chore with two independent cadences: how often it needs doing
    (task_interval_days) and how often the responsible person changes. The latter is either
    set per-duty (rotation_interval_days + assignees below) or inherited from a DutyTeam
    (team_id set) — never both: a team-attached duty ignores its own rotation_interval_days
    and assignees entirely in favor of the team's chore-wheel rotation.
    """

    __tablename__ = "duty"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(String(150))
    description: Mapped[str | None] = mapped_column(Text, default=None)

    start_date: Mapped[date] = mapped_column(Date)
    task_interval_days: Mapped[int] = mapped_column(Integer)
    # Null when team_id is set — the team's rotation_interval_days governs instead.
    rotation_interval_days: Mapped[int | None] = mapped_column(Integer, default=None)

    # CASCADE, not SET NULL: a team-attached duty has no rotation_interval_days or assignees
    # of its own, so detaching it from a deleted team would leave it in a broken,
    # unresolvable state rather than a merely-unconfigured one. Deleting a team is
    # understood to delete its duties too.
    team_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("duty_team.id", ondelete="CASCADE"), default=None, index=True
    )

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
    team: Mapped["DutyTeam | None"] = relationship(back_populates="duties")


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
