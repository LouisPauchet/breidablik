from unittest.mock import AsyncMock

from app.config import get_settings


async def test_cron_tick_rejects_missing_secret(client):
    resp = await client.post("/internal/cron/tick")
    assert resp.status_code == 403


async def test_cron_tick_rejects_wrong_secret(client):
    resp = await client.post("/internal/cron/tick", headers={"X-Cron-Secret": "wrong"})
    assert resp.status_code == 403


async def test_cron_tick_accepts_correct_secret(client, monkeypatch):
    import app.routers.internal as internal_module

    monkeypatch.setattr(internal_module, "run_all_reminders", AsyncMock())

    settings = get_settings()
    resp = await client.post(
        "/internal/cron/tick", headers={"X-Cron-Secret": settings.cron_secret}
    )
    assert resp.status_code == 200
    assert resp.json() == {"ok": True}
    internal_module.run_all_reminders.assert_awaited_once()
