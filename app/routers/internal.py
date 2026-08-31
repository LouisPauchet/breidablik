"""Deliberately outside /api and outside normal user auth — this is how Passenger shared
hosting drives reminders, since it can't be trusted to keep an in-process scheduler alive
(see app/services/reminders.py and the APScheduler wiring in app/main.py, which covers the
Docker case instead). Protected by a shared secret rather than a user session, since the
caller is a cron job, not a logged-in member.
"""

import hmac

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db import get_session
from app.services.reminders import run_all_reminders

router = APIRouter(tags=["internal"])


@router.post("/internal/cron/tick")
async def cron_tick(x_cron_secret: str = Header(default=""), session: AsyncSession = Depends(get_session)):
    settings = get_settings()
    if not settings.cron_secret or not hmac.compare_digest(x_cron_secret, settings.cron_secret):
        raise HTTPException(status_code=403, detail="FORBIDDEN")

    await run_all_reminders(session)

    return {"ok": True}
