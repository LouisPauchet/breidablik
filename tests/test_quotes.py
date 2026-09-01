async def test_quote_of_the_day_requires_auth(client):
    resp = await client.get("/api/quote-of-the-day")
    assert resp.status_code == 401


async def test_quote_of_the_day_returns_text_and_author(client, alice):
    await client.post(
        "/api/auth/login",
        json={"email": "alice@example.com", "password": "correcthorsebatterystaple"},
    )

    resp = await client.get("/api/quote-of-the-day")
    assert resp.status_code == 200
    body = resp.json()
    assert body["text"]
    assert body["author"]


async def test_quote_of_the_day_is_stable_within_the_same_day(client, alice):
    await client.post(
        "/api/auth/login",
        json={"email": "alice@example.com", "password": "correcthorsebatterystaple"},
    )

    first = await client.get("/api/quote-of-the-day")
    second = await client.get("/api/quote-of-the-day")
    assert first.json() == second.json()
