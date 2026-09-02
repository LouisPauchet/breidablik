import pyotp


async def test_login_without_2fa_returns_session(client, alice):
    resp = await client.post(
        "/api/auth/login",
        json={"email": "alice@example.com", "password": "correcthorsebatterystaple"},
    )
    assert resp.status_code == 200
    assert resp.json()["user"]["email"] == "alice@example.com"

    me = await client.get("/api/auth/me")
    assert me.status_code == 200


async def test_login_bad_password_rejected(client, alice):
    resp = await client.post(
        "/api/auth/login",
        json={"email": "alice@example.com", "password": "wrong"},
    )
    assert resp.status_code == 400


async def _login(client):
    return await client.post(
        "/api/auth/login",
        json={"email": "alice@example.com", "password": "correcthorsebatterystaple"},
    )


async def _enroll_totp(client) -> str:
    start = await client.post("/api/auth/2fa/enroll/start")
    secret = start.json()["secret"]
    code = pyotp.TOTP(secret).now()
    confirm = await client.post("/api/auth/2fa/enroll/confirm", json={"code": code})
    assert confirm.status_code == 200
    return secret


async def test_login_gated_behind_2fa_when_enabled(client, alice):
    await _login(client)
    secret = await _enroll_totp(client)
    await client.post("/api/auth/logout")

    # A fresh login attempt (2FA now enabled) must pause for the code, not issue a session.
    resp = await _login(client)
    assert resp.status_code == 200
    assert resp.json() == {"requires_2fa": True}

    me = await client.get("/api/auth/me")
    assert me.status_code == 401

    wrong = await client.post("/api/auth/login/2fa", json={"code": "000000"})
    assert wrong.status_code == 400

    code = pyotp.TOTP(secret).now()
    ok = await client.post("/api/auth/login/2fa", json={"code": code})
    assert ok.status_code == 200

    me = await client.get("/api/auth/me")
    assert me.status_code == 200


async def test_2fa_lockout_after_repeated_failures(client, alice):
    await _login(client)
    secret = await _enroll_totp(client)
    await client.post("/api/auth/logout")

    await _login(client)  # requires_2fa: true, sets the pending-2FA cookie

    for _ in range(5):
        resp = await client.post("/api/auth/login/2fa", json={"code": "000000"})
        assert resp.status_code == 400

    # Even the correct code is now rejected while locked out — and this isn't defeated by
    # the pending token being fresh, since the lockout is tracked on the user, not the token.
    code = pyotp.TOTP(secret).now()
    locked = await client.post("/api/auth/login/2fa", json={"code": code})
    assert locked.status_code == 423
    assert locked.json()["detail"] == "2FA_LOCKED"


async def test_2fa_failure_counter_resets_on_success(client, alice, test_engine):
    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import async_sessionmaker

    from app.models.user import User

    await _login(client)
    secret = await _enroll_totp(client)
    await client.post("/api/auth/logout")

    await _login(client)
    await client.post("/api/auth/login/2fa", json={"code": "000000"})

    code = pyotp.TOTP(secret).now()
    ok = await client.post("/api/auth/login/2fa", json={"code": code})
    assert ok.status_code == 200

    maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with maker() as session:
        result = await session.execute(select(User).where(User.id == alice.id))
        user = result.scalar_one()
        assert user.totp_failed_attempts == 0
        assert user.totp_locked_until is None


async def test_pin_login_bypasses_password_and_2fa(client, alice):
    await _login(client)
    await _enroll_totp(client)

    enroll = await client.post(
        "/api/auth/device-trust/enroll", json={"pin": "1234", "device_label": "test-device"}
    )
    assert enroll.status_code == 200

    logout = await client.post("/api/auth/logout")
    assert logout.status_code == 204

    me = await client.get("/api/auth/me")
    assert me.status_code == 401

    pin_login = await client.post("/api/auth/login/pin", json={"pin": "1234"})
    assert pin_login.status_code == 200
    assert pin_login.json()["user"]["email"] == "alice@example.com"

    me = await client.get("/api/auth/me")
    assert me.status_code == 200


async def test_pin_login_without_trusted_device_rejected(client, alice):
    resp = await client.post("/api/auth/login/pin", json={"pin": "1234"})
    assert resp.status_code == 400
    assert resp.json()["detail"] == "NO_TRUSTED_DEVICE"


async def test_pin_lockout_after_repeated_failures(client, alice):
    await _login(client)
    await client.post(
        "/api/auth/device-trust/enroll", json={"pin": "1234", "device_label": "test-device"}
    )
    await client.post("/api/auth/logout")

    for _ in range(5):
        resp = await client.post("/api/auth/login/pin", json={"pin": "9999"})
        assert resp.status_code == 400
        assert resp.json()["detail"] == "INVALID_PIN"

    # Even the correct PIN is now rejected while locked out.
    locked = await client.post("/api/auth/login/pin", json={"pin": "1234"})
    assert locked.status_code == 423
    assert locked.json()["detail"] == "DEVICE_LOCKED"


async def test_device_trust_status_false_when_no_cookie(client, alice):
    await _login(client)
    resp = await client.get("/api/auth/device-trust/status")
    assert resp.status_code == 200
    assert resp.json() == {"trusted": False}


async def test_device_trust_status_true_after_enrollment(client, alice):
    await _login(client)
    enroll = await client.post(
        "/api/auth/device-trust/enroll", json={"pin": "1234", "device_label": "test-device"}
    )
    assert enroll.status_code == 200

    status = await client.get("/api/auth/device-trust/status")
    assert status.json() == {"trusted": True, "device_label": "test-device"}


async def test_device_trust_status_false_after_revoke(client, alice):
    await _login(client)
    await client.post("/api/auth/device-trust/enroll", json={"pin": "1234"})
    revoke = await client.post("/api/auth/device-trust/revoke")
    assert revoke.status_code == 200

    status = await client.get("/api/auth/device-trust/status")
    assert status.json() == {"trusted": False}


async def test_pin_below_minimum_length_rejected(client, alice):
    await _login(client)
    resp = await client.post("/api/auth/device-trust/enroll", json={"pin": "12"})
    assert resp.status_code == 422
