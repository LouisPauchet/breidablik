import secrets
import uuid
from datetime import date, datetime

from fastapi_users.db import SQLAlchemyBaseUserTableUUID
from fastapi_users_db_sqlalchemy.access_token import SQLAlchemyBaseAccessTokenTableUUID
from sqlalchemy import Date, ForeignKey, Integer, String, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class User(SQLAlchemyBaseUserTableUUID, Base):
    __tablename__ = "user"

    display_name: Mapped[str] = mapped_column(String(100))

    # Year is kept (not just month/day) since it's the simplest thing that stores a real
    # date — the birthday display only ever uses the month/day part. Non-admins are asked to
    # fill this in until they do; admins can dismiss that prompt (see app/routers/members.py).
    birthday: Mapped[date | None] = mapped_column(Date, default=None)

    # 2FA (TOTP). totp_secret is only persisted once enrollment is confirmed with a valid
    # code — never left in a half-enabled state. totp_recovery_codes is a JSON-encoded list
    # of hashed one-time recovery codes.
    totp_secret: Mapped[str | None] = mapped_column(String(64), default=None)
    is_2fa_enabled: Mapped[bool] = mapped_column(default=False)
    totp_recovery_codes: Mapped[str | None] = mapped_column(Text, default=None)

    # Secret used in the per-user ICS subscription URL (/calendar/{token}.ics). Regenerable
    # from Profile if it ever leaks, since calendar apps fetch it unauthenticated.
    calendar_feed_token: Mapped[str] = mapped_column(
        String(64), unique=True, index=True, default=lambda: secrets.token_urlsafe(32)
    )

    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    device_trusts: Mapped[list["DeviceTrust"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class DeviceTrust(Base):
    """A device the user has explicitly opted to trust after a full password(+2FA) login,
    allowing a quick PIN unlock on that device without re-running the full flow. Attempt
    counters live here in the DB (not in-process memory) since Passenger/production may run
    multiple worker processes.
    """

    __tablename__ = "device_trust"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("user.id", ondelete="CASCADE"), index=True)

    device_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    device_label: Mapped[str | None] = mapped_column(String(100), default=None)
    pin_hash: Mapped[str] = mapped_column(String(255))

    failed_pin_attempts: Mapped[int] = mapped_column(Integer, default=0)
    locked_until: Mapped[datetime | None] = mapped_column(default=None)

    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    last_used_at: Mapped[datetime | None] = mapped_column(default=None)
    revoked_at: Mapped[datetime | None] = mapped_column(default=None)

    user: Mapped["User"] = relationship(back_populates="device_trusts")


class AccessToken(SQLAlchemyBaseAccessTokenTableUUID, Base):
    """Opaque, DB-backed session token (fastapi-users DatabaseStrategy) — chosen over a bare
    JWT specifically so a session can be revoked instantly (e.g. via DeviceTrust removal or
    a password change), which a stateless JWT can't do before its own expiry.
    """

    __tablename__ = "access_token"
