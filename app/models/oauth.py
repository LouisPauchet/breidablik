import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, String, UniqueConstraint, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class OAuthAccount(Base):
    """A Google/GitHub identity a member has linked to their existing account (see
    app/auth/oauth.py). The (provider, account_id) pair is the identity — the email is only
    kept for display, since providers let people change it.
    """

    __tablename__ = "oauth_account"
    __table_args__ = (
        UniqueConstraint("provider", "account_id", name="uq_oauth_account_identity"),
        UniqueConstraint("user_id", "provider", name="uq_oauth_account_user_provider"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("user.id", ondelete="CASCADE"), index=True)
    provider: Mapped[str] = mapped_column(String(20))
    account_id: Mapped[str] = mapped_column(String(255))
    account_email: Mapped[str | None] = mapped_column(String(255), default=None)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
