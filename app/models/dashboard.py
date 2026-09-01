import secrets

from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class DashboardConfig(Base):
    """Single-row table (id is always 1) holding the shared secret for the collective's
    wall-display dashboard (see app/routers/dashboard.py). Unlike calendar_feed_token this
    isn't tied to one member — the dashboard only ever shows information the whole household
    can already see, so any signed-in member can view or regenerate this link from Profile.
    """

    __tablename__ = "dashboard_config"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    token: Mapped[str] = mapped_column(
        String(64), unique=True, index=True, default=lambda: secrets.token_urlsafe(32)
    )
