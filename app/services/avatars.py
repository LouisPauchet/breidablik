"""Profile picture storage: one square JPEG per user on local disk under
settings.avatar_storage_dir, named by user id. No column stores the image itself —
User.avatar_updated_at both flags whether one exists (None = no avatar) and cache-busts the
serving URL after a re-upload.
"""

import io
import uuid
from pathlib import Path

from PIL import Image, ImageOps

from app.config import get_settings

_AVATAR_SIZE = 256

ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp"}


def _avatar_path(user_id: uuid.UUID) -> Path:
    return Path(get_settings().avatar_storage_dir) / f"{user_id}.jpg"


def save_avatar(user_id: uuid.UUID, file_bytes: bytes) -> None:
    """Raises PIL.UnidentifiedImageError if file_bytes isn't a decodable image."""
    image = Image.open(io.BytesIO(file_bytes))
    image = ImageOps.exif_transpose(image)  # respect phone-camera orientation metadata
    image = image.convert("RGB")

    # Center-crop to square before resizing so an off-square photo doesn't get squashed.
    width, height = image.size
    side = min(width, height)
    left = (width - side) // 2
    top = (height - side) // 2
    image = image.crop((left, top, left + side, top + side))
    image = image.resize((_AVATAR_SIZE, _AVATAR_SIZE), Image.LANCZOS)

    path = _avatar_path(user_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path, format="JPEG", quality=85)


def delete_avatar(user_id: uuid.UUID) -> None:
    _avatar_path(user_id).unlink(missing_ok=True)


def avatar_file_path(user_id: uuid.UUID) -> Path:
    return _avatar_path(user_id)
