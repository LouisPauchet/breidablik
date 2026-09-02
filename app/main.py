import logging
from contextlib import asynccontextmanager
from pathlib import Path

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.auth.backend import fastapi_users
from app.auth.routes import router as auth_router
from app.config import get_settings
from app.db import session_scope
from app.routers.absences import router as absences_router
from app.routers.admin import router as admin_router
from app.routers.avatars import router as avatars_router
from app.routers.awards import router as awards_router
from app.routers.calendar_feed import router as calendar_feed_router
from app.routers.dashboard import router as dashboard_router
from app.routers.duties import router as duties_router
from app.routers.duty_teams import router as duty_teams_router
from app.routers.events import router as events_router
from app.routers.internal import router as internal_router
from app.routers.members import router as members_router
from app.routers.notifications import router as notifications_router
from app.routers.quotes import router as quotes_router
from app.routers.shopping import router as shopping_router
from app.routers.tasks import router as tasks_router
from app.schemas.user import UserRead, UserUpdate
from app.services.awards import run_award_cycle_tick
from app.services.reminders import run_all_reminders
from app.version import get_version

settings = get_settings()
logger = logging.getLogger(__name__)

_scheduler: AsyncIOScheduler | None = None


async def _scheduled_reminder_tick() -> None:
    async with session_scope() as session:
        await run_all_reminders(session)
        await run_award_cycle_tick(session)


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _scheduler
    # Docker only: a genuinely long-running process can safely host an in-process scheduler.
    # Passenger may recycle/idle its worker process, so it relies on the shared host's own
    # cron hitting POST /internal/cron/tick instead (see app/routers/internal.py) — leave
    # this flag off there.
    if settings.enable_internal_scheduler:
        _scheduler = AsyncIOScheduler()
        _scheduler.add_job(_scheduled_reminder_tick, "interval", minutes=20)
        _scheduler.start()
        logger.info("Internal reminder scheduler started (every 20 min)")
    yield
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)


app = FastAPI(title="Breidablik", lifespan=lifespan)

# All JSON API routes must be included before the SPA catch-all below, since Starlette
# matches routes in registration order and the catch-all would otherwise swallow them. The
# same applies to the two deliberately-plain, non-/api routes (calendar feed, cron tick) —
# especially the calendar feed, whose GET /calendar/{token}.ics would otherwise be caught by
# the SPA fallback's own GET {full_path:path} pattern.
app.include_router(auth_router)
app.include_router(admin_router)
app.include_router(avatars_router)
app.include_router(awards_router)
app.include_router(dashboard_router)
app.include_router(duties_router)
app.include_router(duty_teams_router)
app.include_router(members_router)
app.include_router(absences_router)
app.include_router(tasks_router)
app.include_router(events_router)
app.include_router(shopping_router)
app.include_router(notifications_router)
app.include_router(quotes_router)
app.include_router(calendar_feed_router)
app.include_router(internal_router)
app.include_router(
    fastapi_users.get_users_router(UserRead, UserUpdate),
    prefix="/api/users",
    tags=["users"],
)


@app.get("/api/health")
async def health() -> dict:
    return {"status": "ok"}


@app.get("/api/version")
async def version() -> dict:
    return {"version": get_version()}


frontend_dist = Path(settings.frontend_dist_dir)


def resolve_within(base: Path, relative: str) -> Path | None:
    """Resolve `relative` against `base`, returning None if the result would escape `base`.

    `relative` here is attacker-controlled (a route's {path:path} parameter) and Starlette's
    path converter does not strip `..` segments before matching, so a naive join (base /
    relative) lets a request like `/../../.env` read any file the process can access.
    Resolving both sides and checking containment closes that off regardless of how many
    `..` segments are used or how they're encoded.
    """
    candidate = (base / relative).resolve()
    if not candidate.is_relative_to(base.resolve()):
        return None
    return candidate


if frontend_dist.is_dir():
    nuxt_assets_dir = frontend_dist / "_nuxt"
    if nuxt_assets_dir.is_dir():
        app.mount("/_nuxt", StaticFiles(directory=nuxt_assets_dir), name="nuxt-assets")

    @app.get("/{full_path:path}")
    async def spa_fallback(full_path: str) -> FileResponse:
        # Never let an unmatched /api/* path fall through to the SPA shell — that would mask
        # a real 404 (typo'd endpoint, removed route) as a misleading 200 HTML response.
        if full_path == "api" or full_path.startswith("api/"):
            raise HTTPException(status_code=404)

        candidate = resolve_within(frontend_dist, full_path)
        if candidate is None:
            raise HTTPException(status_code=404)

        if full_path:
            if candidate.is_file():
                return FileResponse(candidate)
            if (candidate / "index.html").is_file():
                return FileResponse(candidate / "index.html")
        return FileResponse(frontend_dist / "index.html")
