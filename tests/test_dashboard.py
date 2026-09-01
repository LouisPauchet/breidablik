from datetime import date, datetime, timedelta, timezone


async def _login(client, email: str):
    resp = await client.post(
        "/api/auth/login", json={"email": email, "password": "correcthorsebatterystaple"}
    )
    assert resp.status_code == 200


async def test_dashboard_link_requires_auth(client):
    resp = await client.get("/api/dashboard/link")
    assert resp.status_code == 401


async def test_dashboard_link_is_stable_then_regenerates(client, alice):
    await _login(client, "alice@example.com")

    first = await client.get("/api/dashboard/link")
    assert first.status_code == 200
    token1 = first.json()["token"]

    second = await client.get("/api/dashboard/link")
    assert second.json()["token"] == token1

    regenerated = await client.post("/api/dashboard/link/regenerate")
    assert regenerated.status_code == 200
    token2 = regenerated.json()["token"]
    assert token2 != token1


async def test_dashboard_data_rejects_unknown_token(client):
    resp = await client.get("/api/dashboard/not-a-real-token")
    assert resp.status_code == 404


async def test_dashboard_data_is_public_and_reflects_on_duty_and_events(client, alice):
    await _login(client, "alice@example.com")
    link = await client.get("/api/dashboard/link")
    token = link.json()["token"]

    await client.post(
        "/api/duties",
        json={
            "title": "Bathroom",
            "start_date": date.today().isoformat(),
            "task_interval_days": 7,
            "rotation_interval_days": 7,
            "assignee_user_ids": [str(alice.id)],
        },
    )
    start = datetime.now(timezone.utc) + timedelta(days=2)
    await client.post("/api/events", json={"title": "Dinner party", "start_at": start.isoformat()})

    await client.post("/api/auth/logout")

    resp = await client.get(f"/api/dashboard/{token}")
    assert resp.status_code == 200
    body = resp.json()

    assert "text" in body["quote"] and "author" in body["quote"]

    on_duty_titles = [d["duty_title"] for d in body["on_duty_today"]]
    assert "Bathroom" in on_duty_titles
    bathroom_entry = next(d for d in body["on_duty_today"] if d["duty_title"] == "Bathroom")
    assert bathroom_entry["assignee_display_name"] == "Alice"

    upcoming_titles = [u["title"] for u in body["upcoming"]]
    assert "Dinner party" in upcoming_titles

    activity_texts = " ".join(a["text"] for a in body["activity"])
    assert "Dinner party" in activity_texts


async def test_dashboard_avatar_rejects_unknown_token(client, alice):
    resp = await client.get(f"/api/dashboard/not-a-real-token/avatar/{alice.id}")
    assert resp.status_code == 404


async def test_dashboard_avatar_404_when_none_uploaded(client, alice):
    await _login(client, "alice@example.com")
    link = await client.get("/api/dashboard/link")
    token = link.json()["token"]

    resp = await client.get(f"/api/dashboard/{token}/avatar/{alice.id}")
    assert resp.status_code == 404
