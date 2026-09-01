import uuid
from datetime import date, datetime

from sqlalchemy import Boolean, Date, ForeignKey, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Absence(Base):
    """A member marking themselves away. Rendered as a band on the collective calendar and
    used to flag duty occurrences assigned to someone away. By default that's just a flag for
    a human to act on (see app/services/absences.py:is_user_away) — auto_reassign opts a
    specific absence into automatically handing off already-assigned occurrences instead (see
    app/services/auto_reassign.py).
    """

    __tablename__ = "absence"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("user.id", ondelete="CASCADE"), index=True)
    start_date: Mapped[date] = mapped_column(Date, index=True)
    end_date: Mapped[date] = mapped_column(Date, index=True)
    reason: Mapped[str | None] = mapped_column(String(255), default=None)
    auto_reassign: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
