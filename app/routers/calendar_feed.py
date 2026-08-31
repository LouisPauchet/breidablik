from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models.user import User
from app.services.calendar_feed import build_ics_for_user

router = APIRouter(tags=["calendar-feed"])


@router.get("/calendar/{token}.ics")
async def get_calendar_feed(token: str, session: AsyncSession = Depends(get_session)):
    result = await session.execute(select(User).where(User.calendar_feed_token == token))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=404, detail="NOT_FOUND")

    ics_bytes = await build_ics_for_user(session, user)
    return Response(content=ics_bytes, media_type="text/calendar; charset=utf-8")
