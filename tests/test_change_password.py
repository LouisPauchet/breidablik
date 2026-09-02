from httpx import ASGITransport, AsyncClient

from app.main import app


async def _login(client, email: str, password: str = "correcthorsebatterystaple"):
    resp = await client.post("/api/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200


async def test_change_password_requires_auth(client):
    resp = await client.post(
        "/api/auth/change-password",
        json={"current_password": "x", "new_password": "newpassword123"},
    )
    assert resp.status_code == 401


async def test_change_password_rejects_wrong_current_password(client, alice):
    await _login(client, "alice@example.com")
    resp = await client.post(
        "/api/auth/change-password",
        json={"current_password": "wrongpassword", "new_password": "newpassword123"},
    )
    assert resp.status_code == 400


async def test_change_password_succeeds_and_new_password_works(client, alice):
    await _login(client, "alice@example.com")
    resp = await client.post(
        "/api/auth/change-password",
        json={"current_password": "correcthorsebatterystaple", "new_password": "newpassword123"},
    )
    assert resp.status_code == 200

    await client.post("/api/auth/logout")

    old_login = await client.post(
        "/api/auth/login", json={"email": "alice@example.com", "password": "correcthorsebatterystaple"}
    )
    assert old_login.status_code == 400

    new_login = await client.post(
        "/api/auth/login", json={"email": "alice@example.com", "password": "newpassword123"}
    )
    assert new_login.status_code == 200


async def test_change_password_keeps_current_session_logged_in(client, alice):
    await _login(client, "alice@example.com")
    await client.post(
        "/api/auth/change-password",
        json={"current_password": "correcthorsebatterystaple", "new_password": "newpassword123"},
    )
    # Same client/cookie jar, no re-login — the session used to make the change survives.
    me = await client.get("/api/auth/me")
    assert me.status_code == 200
    assert me.json()["email"] == "alice@example.com"


async def test_change_password_logs_out_every_other_session(client, alice):
    # A second, already-logged-in "device" — its own cookie jar, same backing DB via the
    # shared app + dependency override the `client` fixture already installed.
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as other_device:
        await _login(other_device, "alice@example.com")
        assert (await other_device.get("/api/auth/me")).status_code == 200

        await _login(client, "alice@example.com")
        resp = await client.post(
            "/api/auth/change-password",
            json={"current_password": "correcthorsebatterystaple", "new_password": "newpassword123"},
        )
        assert resp.status_code == 200

        # A stolen/other-device session must not survive the account holder changing their
        # password — this is the actual security property being fixed.
        other_after = await other_device.get("/api/auth/me")
        assert other_after.status_code == 401
