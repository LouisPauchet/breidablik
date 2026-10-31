"""Safety checks shared by the admin member-management actions (see app/routers/admin.py)."""

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User


def assert_not_self(actor: User, target: User) -> None:
    if actor.id == target.id:
        raise HTTPException(status_code=400, detail="CANNOT_ACT_ON_SELF")


async def assert_not_last_admin(session: AsyncSession, target: User) -> None:
    """Call before demoting or deactivating `target`: the household must always keep at least
    one active admin. Inactive admins (pending invite, deactivated) can't run anything, so
    they don't count toward that.
    """
    if not target.is_superuser:
        return

    result = await session.execute(
        select(func.count())
        .select_from(User)
        .where(User.is_superuser.is_(True), User.is_active.is_(True), User.id != target.id)
    )
    if result.scalar_one() == 0:
        raise HTTPException(status_code=400, detail="LAST_ADMIN")
