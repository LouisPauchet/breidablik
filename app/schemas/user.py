import uuid
from datetime import date, datetime

from fastapi_users import schemas
from pydantic import BaseModel, EmailStr, Field, model_validator


class UserRead(schemas.BaseUser[uuid.UUID]):
    display_name: str
    is_2fa_enabled: bool
    birthday: date | None
    avatar_updated_at: datetime | None
    # Set while an admin has the account deactivated (see app/routers/admin.py).
    deactivated_at: datetime | None = None
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

    @model_validator(mode="after")
    def _no_privileged_flags(self):
        # fastapi-users' stock PATCH /api/users/{id} lets any admin flip these on anyone,
        # including themselves, which would skip the guards and audit trail of the admin
        # endpoints (deactivate/reactivate/role in app/routers/admin.py) — use those instead.
        if self.is_active is not None or self.is_superuser is not None:
            raise ValueError("is_active and is_superuser are changed through /api/admin/users/{id}/...")
        return self


class AdminUserInvite(BaseModel):
    """No password field — an admin invites a member by name/email only; the member sets
    their own password by following the invite link (see app/auth/routes.py)."""

    display_name: str = Field(min_length=1, max_length=100)
    email: EmailStr
    is_superuser: bool = False


class AdminRoleChange(BaseModel):
    is_superuser: bool


class AdminPasswordResetRequest(BaseModel):
    """`reset_2fa` is carried inside the signed link and only applied when the member redeems
    it — see app/routers/admin.py."""

    reset_2fa: bool = False


class AdminPasswordResetResponse(BaseModel):
    token: str
    expires_in: int


class AuditLogEntry(BaseModel):
    id: uuid.UUID
    actor_id: uuid.UUID | None
    actor_name: str | None
    target_user_id: uuid.UUID | None
    target_name: str | None
    action: str
    detail: dict | None
    created_at: datetime
