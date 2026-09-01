from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.models.user import User


async def _login(client, email: str, password: str = "correcthorsebatterystaple"):
    resp = await client.post("/api/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200


async def test_get_invite_returns_name_and_email(client, alice):
    await _login(client, "alice@example.com")
    create_resp = await client.post(
        "/api/admin/users", json={"email": "carol@example.com", "display_name": "Carol"}
    )
    token = create_resp.json()["invite_token"]
    await client.post("/api/auth/logout")

    resp = await client.get(f"/api/auth/invite/{token}")
    assert resp.status_code == 200
    assert resp.json() == {"display_name": "Carol", "email": "carol@example.com"}


async def test_unknown_invite_token_404s(client):
    resp = await client.get("/api/auth/invite/does-not-exist")
    assert resp.status_code == 404


async def test_expired_invite_token_rejected(client, alice, test_engine):
    await _login(client, "alice@example.com")
    create_resp = await client.post(
        "/api/admin/users", json={"email": "carol@example.com", "display_name": "Carol"}
    )
    token = create_resp.json()["invite_token"]

    maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with maker() as session:
        result = await session.execute(select(User).where(User.invite_token == token))
        user = result.scalar_one()
        user.invite_token_expires_at = datetime.now(timezone.utc) - timedelta(days=1)
        await session.commit()

    resp = await client.get(f"/api/auth/invite/{token}")
    assert resp.status_code == 410

    accept = await client.post(f"/api/auth/invite/{token}/accept", json={"password": "brandnewpassword"})
    assert accept.status_code == 410


async def test_accepting_invite_clears_token_and_prevents_reuse(client, alice):
    await _login(client, "alice@example.com")
    create_resp = await client.post(
        "/api/admin/users", json={"email": "carol@example.com", "display_name": "Carol"}
    )
    token = create_resp.json()["invite_token"]
    await client.post("/api/auth/logout")

    first = await client.post(f"/api/auth/invite/{token}/accept", json={"password": "brandnewpassword"})
    assert first.status_code == 200
    await client.post("/api/auth/logout")

    second = await client.post(f"/api/auth/invite/{token}/accept", json={"password": "somethingelse123"})
    assert second.status_code == 404
