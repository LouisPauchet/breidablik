"""Deliberately outside /api and outside normal user auth — this is how Passenger shared
hosting drives things that would otherwise need a persistent in-process scheduler (reminders)
or an external caller (the update script), since a Passenger worker can't be trusted to stay
alive or to be reachable except via HTTP (see app/services/reminders.py and the APScheduler
wiring in app/main.py, which covers the Docker case instead). Protected by a shared secret
rather than a user session, since the caller is a cron job or a deploy script, not a logged-in
member.
"""

import hmac

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db import get_session
from app.services.awards import run_award_cycle_tick
from app.services.notifications import notify_admins_of_update
from app.services.reminders import run_all_reminders

router = APIRouter(tags=["internal"])


def _require_cron_secret(x_cron_secret: str) -> None:
    settings = get_settings()
    if not settings.cron_secret or not hmac.compare_digest(x_cron_secret, settings.cron_secret):
        raise HTTPException(status_code=403, detail="FORBIDDEN")


@router.post("/internal/cron/tick")
async def cron_tick(x_cron_secret: str = Header(default=""), session: AsyncSession = Depends(get_session)):
    _require_cron_secret(x_cron_secret)
    await run_all_reminders(session)
    await run_award_cycle_tick(session)
    return {"ok": True}


class NotifyUpdateIn(BaseModel):
    version: str


@router.post("/internal/cron/notify-update")
async def notify_update(
    data: NotifyUpdateIn,
    x_cron_secret: str = Header(default=""),
    session: AsyncSession = Depends(get_session),
):
    """Called by scripts/passenger_update.py right after it finishes applying a new release,
    so admins learn the app was updated without needing to notice a version number changed.
    """
    _require_cron_secret(x_cron_secret)
    await notify_admins_of_update(session, data.version)
    return {"ok": True}
