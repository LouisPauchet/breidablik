from datetime import date, datetime, timedelta, timezone

from icalendar import Calendar


async def test_feed_requires_valid_token(client):
    resp = await client.get("/calendar/not-a-real-token.ics")
    assert resp.status_code == 404


async def test_feed_returns_calendar_content_type(client, alice):
    resp = await client.get(f"/calendar/{alice.calendar_feed_token}.ics")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/calendar")


async def test_feed_includes_own_duty_occurrence(client, alice):
    await client.post(
        "/api/auth/login",
        json={"email": "alice@example.com", "password": "correcthorsebatterystaple"},
    )
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

    resp = await client.get(f"/calendar/{alice.calendar_feed_token}.ics")
    cal = Calendar.from_ical(resp.content)
    summaries = [str(c.get("summary")) for c in cal.walk("VEVENT")]
    assert "Bathroom" in summaries


async def test_feed_includes_collective_events_regardless_of_assignment(client, alice):
    await client.post(
        "/api/auth/login",
        json={"email": "alice@example.com", "password": "correcthorsebatterystaple"},
    )
    start = datetime.now(timezone.utc) + timedelta(days=2)
    await client.post("/api/events", json={"title": "Dinner party", "start_at": start.isoformat()})

    resp = await client.get(f"/calendar/{alice.calendar_feed_token}.ics")
    cal = Calendar.from_ical(resp.content)
    summaries = [str(c.get("summary")) for c in cal.walk("VEVENT")]
    assert "Dinner party" in summaries


async def test_feed_includes_absences_as_transparent(client, alice):
    await client.post(
        "/api/auth/login",
        json={"email": "alice@example.com", "password": "correcthorsebatterystaple"},
    )
    await client.post(
        "/api/absences",
        json={"start_date": date.today().isoformat(), "end_date": date.today().isoformat(), "reason": "Trip"},
    )

    resp = await client.get(f"/calendar/{alice.calendar_feed_token}.ics")
    cal = Calendar.from_ical(resp.content)
    away_events = [c for c in cal.walk("VEVENT") if "away" in str(c.get("summary"))]
    assert len(away_events) == 1
    assert str(away_events[0].get("transp")) == "TRANSPARENT"


async def test_feed_uid_stable_across_refetches(client, alice):
    await client.post(
        "/api/auth/login",
        json={"email": "alice@example.com", "password": "correcthorsebatterystaple"},
    )
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

    resp1 = await client.get(f"/calendar/{alice.calendar_feed_token}.ics")
    resp2 = await client.get(f"/calendar/{alice.calendar_feed_token}.ics")

    uids1 = {str(c.get("uid")) for c in Calendar.from_ical(resp1.content).walk("VEVENT")}
    uids2 = {str(c.get("uid")) for c in Calendar.from_ical(resp2.content).walk("VEVENT")}
    assert uids1 == uids2
    assert len(uids1) > 0
