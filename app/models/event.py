import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, String, Text, UniqueConstraint, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class EventType(str, enum.Enum):
    dinner = "dinner"
    party = "party"
    meeting = "meeting"
    other = "other"


class RSVPStatus(str, enum.Enum):
    yes = "yes"
    no = "no"
    maybe = "maybe"


class EventSeries(Base):
    """Groups related events together (e.g. a MasterChef-style dinner series). Grouping
    only — no scoring/leaderboard, that wasn't asked for.
    """

    __tablename__ = "event_series"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(150))
    description: Mapped[str | None] = mapped_column(Text, default=None)
    created_by_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("user.id"))
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    events: Mapped[list["Event"]] = relationship(back_populates="series")


class Event(Base):
    __tablename__ = "event"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(String(150))
    event_type: Mapped[EventType] = mapped_column(Enum(EventType), default=EventType.other)
    description: Mapped[str | None] = mapped_column(Text, default=None)
    location: Mapped[str | None] = mapped_column(String(255), default=None)

    start_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    end_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)

    series_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("event_series.id", ondelete="SET NULL"), default=None
    )
    reminder_sent_at: Mapped[datetime | None] = mapped_column(default=None)

    created_by_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("user.id"))
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    series: Mapped["EventSeries | None"] = relationship(back_populates="events")
    rsvps: Mapped[list["EventRSVP"]] = relationship(
        back_populates="event", cascade="all, delete-orphan"
    )


class EventRSVP(Base):
    __tablename__ = "event_rsvp"
    __table_args__ = (UniqueConstraint("event_id", "user_id", name="uq_event_rsvp"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    event_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("event.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("user.id", ondelete="CASCADE"))
    status: Mapped[RSVPStatus] = mapped_column(Enum(RSVPStatus))
    responded_at: Mapped[datetime] = mapped_column(server_default=func.now())

    event: Mapped["Event"] = relationship(back_populates="rsvps")
