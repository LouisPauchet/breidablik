import uuid
from datetime import date, datetime

from fastapi_users import schemas
from pydantic import BaseModel, EmailStr, Field


class UserRead(schemas.BaseUser[uuid.UUID]):
    display_name: str
    is_2fa_enabled: bool
    birthday: date | None
    avatar_updated_at: datetime | None
    # Only ever meaningful for an admin looking at a not-yet-accepted invite (see
    # app/routers/admin.py) — None once accepted, or if the account wasn't invite-created.
    invite_token: str | None = None


class UserCreate(schemas.BaseUserCreate):
    display_name: str
    birthday: date | None = None


class UserUpdate(schemas.BaseUserUpdate):
    display_name: str | None = None
    # A plain custom field, not one of fastapi-users' special-cased privileged fields
    # (is_active/is_superuser/is_verified) — so it's already settable by a user on
    # themselves via PATCH /api/users/me without needing superuser rights, no new
    # endpoint required (see BaseUserUpdate.create_update_dict for why).
    birthday: date | None = None


class AdminUserInvite(BaseModel):
    """No password field — an admin invites a member by name/email only; the member sets
    their own password by following the invite link (see app/auth/routes.py)."""

    display_name: str = Field(min_length=1, max_length=100)
    email: EmailStr
    is_superuser: bool = False
