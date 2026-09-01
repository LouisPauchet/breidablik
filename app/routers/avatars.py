"""Profile picture upload/serving. Distinct from fastapi-users' own /api/users/{id} routes,
which are superuser-gated for other users — every member should be able to see everyone
else's avatar (that's the point of it), and only ever change their own.
"""

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from fastapi.responses import FileResponse
from PIL import UnidentifiedImageError
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.backend import current_active_user
from app.config import get_settings
from app.db import get_session
from app.models.user import User
from app.services.avatars import ALLOWED_CONTENT_TYPES, avatar_file_path, delete_avatar, save_avatar

router = APIRouter(prefix="/api/users", tags=["avatars"], dependencies=[Depends(current_active_user)])


@router.post("/me/avatar")
async def upload_my_avatar(
    file: UploadFile,
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_session),
):
    if file.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(status_code=422, detail="UNSUPPORTED_IMAGE_TYPE")

    settings = get_settings()
    data = await file.read(settings.avatar_max_upload_bytes + 1)
    if len(data) > settings.avatar_max_upload_bytes:
        raise HTTPException(status_code=413, detail="IMAGE_TOO_LARGE")

    try:
        save_avatar(user.id, data)
    except UnidentifiedImageError:
        raise HTTPException(status_code=422, detail="INVALID_IMAGE") from None

    user.avatar_updated_at = datetime.now(timezone.utc)
    await session.commit()
    return {"avatar_updated_at": user.avatar_updated_at}


@router.delete("/me/avatar", status_code=204)
async def remove_my_avatar(
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_session),
):
    delete_avatar(user.id)
    user.avatar_updated_at = None
    await session.commit()


@router.get("/{user_id}/avatar")
async def get_avatar(user_id: uuid.UUID):
    path = avatar_file_path(user_id)
    if not path.is_file():
        raise HTTPException(status_code=404, detail="NO_AVATAR")
    return FileResponse(path, media_type="image/jpeg")
