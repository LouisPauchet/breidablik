from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.auth.backend import fastapi_users
from app.auth.routes import router as auth_router
from app.config import get_settings
from app.routers.absences import router as absences_router
from app.routers.admin import router as admin_router
from app.routers.duties import router as duties_router
from app.routers.events import router as events_router
from app.routers.members import router as members_router
from app.routers.tasks import router as tasks_router
from app.schemas.user import UserRead, UserUpdate

settings = get_settings()

app = FastAPI(title="Breidablik")

# All JSON API routes must be included before the SPA catch-all below, since Starlette
# matches routes in registration order and the catch-all would otherwise swallow them.
app.include_router(auth_router)
app.include_router(admin_router)
app.include_router(duties_router)
app.include_router(members_router)
app.include_router(absences_router)
app.include_router(tasks_router)
app.include_router(events_router)
app.include_router(
    fastapi_users.get_users_router(UserRead, UserUpdate),
    prefix="/api/users",
    tags=["users"],
)


@app.get("/api/health")
async def health() -> dict:
    return {"status": "ok"}


frontend_dist = Path(settings.frontend_dist_dir)

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

        candidate = frontend_dist / full_path
        if full_path:
            if candidate.is_file():
                return FileResponse(candidate)
            if (candidate / "index.html").is_file():
                return FileResponse(candidate / "index.html")
        return FileResponse(frontend_dist / "index.html")
