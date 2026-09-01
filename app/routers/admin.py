"""Admin-only member management. Registration is deliberately not public (closed household
app) — an admin invites each member here rather than setting a password for them: the account
is created inactive with a random, never-shared password and an invite link the admin copies
and sends however they like (text, email, in person); the member sets their own real password
by following it (see /api/auth/invite/{token} in app/auth/routes.py).
"""

import secrets
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from fastapi_users.exceptions import UserAlreadyExists
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.backend import current_superuser
from app.auth.users import UserManager, get_user_manager
from app.db import get_session
from app.models.user import User
from app.schemas.user import AdminUserInvite, UserCreate, UserRead

router = APIRouter(prefix="/api/admin", tags=["admin"], dependencies=[Depends(current_superuser)])

INVITE_TOKEN_LIFETIME = timedelta(days=7)


def _issue_invite(user: User) -> None:
    user.invite_token = secrets.token_urlsafe(32)
    user.invite_token_expires_at = datetime.now(timezone.utc) + INVITE_TOKEN_LIFETIME


@router.get("/users", response_model=list[UserRead])
async def list_members(session: AsyncSession = Depends(get_session)):
    """Fuller member info (email, is_active, is_superuser, invite_token) than the public
    /api/members directory exposes — this router is already superuser-gated at the router
    level.
    """
    result = await session.execute(select(User).order_by(User.display_name))
    return list(result.scalars())


@router.post("/users", response_model=UserRead, status_code=201)
async def invite_member(
    data: AdminUserInvite,
    user_manager: UserManager = Depends(get_user_manager),
    session: AsyncSession = Depends(get_session),
):
    try:
        user = await user_manager.create(
            UserCreate(
                email=data.email,
                # Random and never shared with anyone — the account is unusable until the
                # invite is accepted and a real password is set (see accept_invite).
                password=secrets.token_urlsafe(32),
                display_name=data.display_name,
                is_superuser=data.is_superuser,
                is_active=False,
            ),
            safe=False,
        )
    except UserAlreadyExists as exc:
        raise HTTPException(status_code=400, detail="USER_ALREADY_EXISTS") from exc

    _issue_invite(user)
    await session.commit()
    await session.refresh(user)
    return user


@router.post("/users/{user_id}/invite/regenerate", response_model=UserRead)
async def regenerate_invite(user_id: uuid.UUID, session: AsyncSession = Depends(get_session)):
    result = await session.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=404, detail="USER_NOT_FOUND")
    if user.is_active:
        raise HTTPException(status_code=400, detail="USER_ALREADY_ACTIVE")

    _issue_invite(user)
    await session.commit()
    await session.refresh(user)
    return user
