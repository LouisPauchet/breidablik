import uuid
from datetime import date, datetime

from fastapi_users import schemas


class UserRead(schemas.BaseUser[uuid.UUID]):
    display_name: str
    is_2fa_enabled: bool
    birthday: date | None
    avatar_updated_at: datetime | None


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
