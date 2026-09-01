async def test_list_members_requires_auth(client):
    resp = await client.get("/api/members")
    assert resp.status_code == 401


async def test_list_members_returns_display_names(client, alice):
    await client.post(
        "/api/auth/login",
        json={"email": "alice@example.com", "password": "correcthorsebatterystaple"},
    )
    resp = await client.get("/api/members")
    assert resp.status_code == 200
    body = resp.json()
    assert body == [
        {"id": str(alice.id), "display_name": "Alice", "birthday": None, "avatar_updated_at": None}
    ]


async def test_list_members_includes_birthday_once_set(client, alice):
    await client.post(
        "/api/auth/login",
        json={"email": "alice@example.com", "password": "correcthorsebatterystaple"},
    )
    updated = await client.patch("/api/users/me", json={"birthday": "1990-05-15"})
    assert updated.status_code == 200
    assert updated.json()["birthday"] == "1990-05-15"

    resp = await client.get("/api/members")
    assert resp.json()[0]["birthday"] == "1990-05-15"
