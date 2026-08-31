import uuid
from datetime import date, datetime

from sqlalchemy import Date, ForeignKey, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Absence(Base):
    """A member marking themselves away. Rendered as a band on the collective calendar and
    used to flag (not silently auto-resolve) duty occurrences assigned to someone away —
    see app/services/rotation.py:find_away_conflict.
    """

    __tablename__ = "absence"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("user.id", ondelete="CASCADE"), index=True)
    start_date: Mapped[date] = mapped_column(Date, index=True)
    end_date: Mapped[date] = mapped_column(Date, index=True)
    reason: Mapped[str | None] = mapped_column(String(255), default=None)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
