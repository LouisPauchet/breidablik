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
    monkeypatch.setattr(internal_module, "run_award_cycle_tick", AsyncMock())

    settings = get_settings()
    resp = await client.post(
        "/internal/cron/tick", headers={"X-Cron-Secret": settings.cron_secret}
    )
    assert resp.status_code == 200
    assert resp.json() == {"ok": True}
    internal_module.run_all_reminders.assert_awaited_once()
    internal_module.run_award_cycle_tick.assert_awaited_once()


async def test_notify_update_rejects_missing_secret(client):
    resp = await client.post("/internal/cron/notify-update", json={"version": "1.2.3"})
    assert resp.status_code == 403


async def test_notify_update_accepts_correct_secret(client, monkeypatch):
    import app.routers.internal as internal_module

    mock = AsyncMock()
    monkeypatch.setattr(internal_module, "notify_admins_of_update", mock)

    settings = get_settings()
    resp = await client.post(
        "/internal/cron/notify-update",
        json={"version": "1.2.3"},
        headers={"X-Cron-Secret": settings.cron_secret},
    )
    assert resp.status_code == 200
    assert resp.json() == {"ok": True}
    mock.assert_awaited_once()
    assert mock.await_args.args[1] == "1.2.3"
