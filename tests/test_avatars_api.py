import io

import pytest
from PIL import Image

from app.config import get_settings


@pytest.fixture
def isolated_avatar_dir(tmp_path, monkeypatch):
    """Avatars land on local disk keyed by settings.avatar_storage_dir — point that at a
    throwaway tmp_path for the test instead of the project's real (gitignored) var/avatars.
    """
    monkeypatch.setenv("AVATAR_STORAGE_DIR", str(tmp_path))
    get_settings.cache_clear()
    yield tmp_path
    get_settings.cache_clear()


async def _login(client, email: str):
    resp = await client.post(
        "/api/auth/login", json={"email": email, "password": "correcthorsebatterystaple"}
    )
    assert resp.status_code == 200


def _jpeg_bytes(size=(300, 200), color=(255, 0, 0)) -> bytes:
    image = Image.new("RGB", size, color=color)
    buf = io.BytesIO()
    image.save(buf, format="JPEG")
    return buf.getvalue()


async def test_upload_and_fetch_avatar(client, alice, isolated_avatar_dir):
    await _login(client, "alice@example.com")

    upload = await client.post(
        "/api/users/me/avatar", files={"file": ("photo.jpg", _jpeg_bytes(), "image/jpeg")}
    )
    assert upload.status_code == 200
    assert upload.json()["avatar_updated_at"] is not None

    fetch = await client.get(f"/api/users/{alice.id}/avatar")
    assert fetch.status_code == 200
    assert fetch.headers["content-type"] == "image/jpeg"

    me = await client.get("/api/auth/me")
    assert me.json()["avatar_updated_at"] is not None


async def test_avatar_is_resized_and_squared(client, alice, isolated_avatar_dir):
    await _login(client, "alice@example.com")
    await client.post(
        "/api/users/me/avatar", files={"file": ("photo.jpg", _jpeg_bytes((800, 400)), "image/jpeg")}
    )
    saved = Image.open(isolated_avatar_dir / f"{alice.id}.jpg")
    assert saved.size == (256, 256)


async def test_upload_rejects_non_image_content_type(client, alice, isolated_avatar_dir):
    await _login(client, "alice@example.com")
    resp = await client.post(
        "/api/users/me/avatar", files={"file": ("notes.txt", b"hello world", "text/plain")}
    )
    assert resp.status_code == 422


async def test_upload_rejects_oversized_file(client, alice, isolated_avatar_dir, monkeypatch):
    monkeypatch.setenv("AVATAR_MAX_UPLOAD_BYTES", "10")
    get_settings.cache_clear()
    await _login(client, "alice@example.com")
    resp = await client.post(
        "/api/users/me/avatar", files={"file": ("photo.jpg", _jpeg_bytes(), "image/jpeg")}
    )
    assert resp.status_code == 413


async def test_no_avatar_returns_404(client, alice, isolated_avatar_dir):
    await _login(client, "alice@example.com")
    resp = await client.get(f"/api/users/{alice.id}/avatar")
    assert resp.status_code == 404


async def test_delete_avatar(client, alice, isolated_avatar_dir):
    await _login(client, "alice@example.com")
    await client.post(
        "/api/users/me/avatar", files={"file": ("photo.jpg", _jpeg_bytes(), "image/jpeg")}
    )
    delete_resp = await client.delete("/api/users/me/avatar")
    assert delete_resp.status_code == 204

    fetch = await client.get(f"/api/users/{alice.id}/avatar")
    assert fetch.status_code == 404


async def test_other_members_avatar_is_visible(client, alice, isolated_avatar_dir, test_engine):
    from fastapi_users.db import SQLAlchemyUserDatabase
    from sqlalchemy.ext.asyncio import async_sessionmaker

    from app.auth.users import UserManager
    from app.models.user import User
    from app.schemas.user import UserCreate

    maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with maker() as session:
        manager = UserManager(SQLAlchemyUserDatabase(session, User))
        bob = await manager.create(
            UserCreate(email="bob@example.com", password="correcthorsebatterystaple", display_name="Bob"),
            safe=False,
        )

    await _login(client, "alice@example.com")
    await client.post(
        "/api/users/me/avatar", files={"file": ("photo.jpg", _jpeg_bytes(), "image/jpeg")}
    )
    await client.post("/api/auth/logout")

    await _login(client, "bob@example.com")
    fetch = await client.get(f"/api/users/{alice.id}/avatar")
    assert fetch.status_code == 200

    members = await client.get("/api/members")
    alice_row = next(m for m in members.json() if m["id"] == str(alice.id))
    assert alice_row["avatar_updated_at"] is not None
    bob_row = next(m for m in members.json() if m["id"] == str(bob.id))
    assert bob_row["avatar_updated_at"] is None
