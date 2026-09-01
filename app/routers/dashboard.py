"""The wall-display dashboard's backend: a household-wide summary reachable via one shared
secret link rather than a personal login, since it's meant to be opened once on a shared
screen (kitchen tablet, TV) and left running — see app/services/dashboard.py and the
DashboardConfig model. The link/regenerate endpoints are the only auth-gated part of this
router; the data and avatar endpoints are deliberately public, keyed by the token itself,
exactly like the per-user calendar feed (app/routers/calendar_feed.py).
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi.responses import FileResponse

from app.auth.backend import current_active_user
from app.db import get_session
from app.models.dashboard import DashboardConfig
from app.schemas.dashboard import DashboardOut, DashboardTokenOut
from app.services.avatars import avatar_file_path
from app.services.dashboard import build_dashboard_data, get_or_create_dashboard_config, regenerate_dashboard_token

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


async def _load_config_by_token_or_404(session: AsyncSession, token: str) -> DashboardConfig:
    result = await session.execute(select(DashboardConfig).where(DashboardConfig.token == token))
    config = result.scalar_one_or_none()
    if config is None:
        raise HTTPException(status_code=404, detail="NOT_FOUND")
    return config


# Registered before the /{token} routes below so a literal "link" path segment always wins —
# not that a real token (32 bytes, urlsafe-base64) would ever collide with it in practice.
@router.get("/link", response_model=DashboardTokenOut, dependencies=[Depends(current_active_user)])
async def get_dashboard_link(session: AsyncSession = Depends(get_session)):
    config = await get_or_create_dashboard_config(session)
    return DashboardTokenOut(token=config.token)


@router.post("/link/regenerate", response_model=DashboardTokenOut, dependencies=[Depends(current_active_user)])
async def regenerate_dashboard_link(session: AsyncSession = Depends(get_session)):
    config = await regenerate_dashboard_token(session)
    return DashboardTokenOut(token=config.token)


@router.get("/{token}", response_model=DashboardOut)
async def get_dashboard(token: str, session: AsyncSession = Depends(get_session)):
    await _load_config_by_token_or_404(session, token)
    return await build_dashboard_data(session)


@router.get("/{token}/avatar/{user_id}")
async def get_dashboard_avatar(token: str, user_id: uuid.UUID, session: AsyncSession = Depends(get_session)):
    await _load_config_by_token_or_404(session, token)
    path = avatar_file_path(user_id)
    if not path.is_file():
        raise HTTPException(status_code=404, detail="NO_AVATAR")
    return FileResponse(path, media_type="image/jpeg")
