"""Read-only member directory (id + display name) available to any authenticated member —
distinct from /api/users, whose per-id operations are superuser-gated by fastapi-users. The
duty/task/event assignee pickers and the "who's on duty" displays need every member to be
able to see who else is in the collective.
"""

import uuid

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.backend import current_active_user
from app.db import get_session
from app.models.user import User

router = APIRouter(prefix="/api/members", tags=["members"], dependencies=[Depends(current_active_user)])


class MemberOut(BaseModel):
    id: uuid.UUID
    display_name: str


@router.get("", response_model=list[MemberOut])
async def list_members(session: AsyncSession = Depends(get_session)):
    result = await session.execute(
        select(User).where(User.is_active.is_(True)).order_by(User.display_name)
    )
    return list(result.scalars())
