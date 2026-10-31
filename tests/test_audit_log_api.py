from tests.test_admin_api import _create_user, _login


async def _make_history(client, alice, test_engine):
    """Alice deactivates then reactivates Bob, then force-logs-out Carol: three entries."""
    bob = await _create_user(test_engine, "bob@example.com", "Bob")
    carol = await _create_user(test_engine, "carol@example.com", "Carol")
    await _login(client, "alice@example.com")
    await client.post(f"/api/admin/users/{bob.id}/deactivate")
    await client.post(f"/api/admin/users/{bob.id}/reactivate")
    await client.post(f"/api/admin/users/{carol.id}/revoke-sessions")
    return bob, carol


async def test_audit_log_lists_newest_first_with_names(client, alice, test_engine):
    bob, carol = await _make_history(client, alice, test_engine)

    resp = await client.get("/api/admin/audit-log")
    assert resp.status_code == 200
    entries = resp.json()
    assert [e["action"] for e in entries] == [
        "user.sessions_revoked",
        "user.reactivated",
        "user.deactivated",
    ]
    newest = entries[0]
    assert newest["actor_name"] == "Alice"
    assert newest["target_name"] == "Carol"
    assert newest["target_user_id"] == str(carol.id)
    assert newest["created_at"]


async def test_audit_log_detail_is_returned_as_an_object(client, alice, test_engine):
    bob = await _create_user(test_engine, "bob@example.com", "Bob")
    await _login(client, "alice@example.com")
    await client.patch(f"/api/admin/users/{bob.id}/role", json={"is_superuser": True})

    [entry] = (await client.get("/api/admin/audit-log")).json()
    assert entry["detail"] == {"is_superuser": True}


async def test_audit_log_can_filter_by_target(client, alice, test_engine):
    bob, _ = await _make_history(client, alice, test_engine)

    entries = (await client.get(f"/api/admin/audit-log?target={bob.id}")).json()
    assert [e["action"] for e in entries] == ["user.reactivated", "user.deactivated"]
    assert {e["target_name"] for e in entries} == {"Bob"}


async def test_audit_log_pages_with_limit_and_offset(client, alice, test_engine):
    await _make_history(client, alice, test_engine)

    first = (await client.get("/api/admin/audit-log?limit=2")).json()
    assert [e["action"] for e in first] == ["user.sessions_revoked", "user.reactivated"]

    rest = (await client.get("/api/admin/audit-log?limit=2&offset=2")).json()
    assert [e["action"] for e in rest] == ["user.deactivated"]


async def test_audit_log_rejects_an_oversized_limit(client, alice):
    await _login(client, "alice@example.com")
    assert (await client.get("/api/admin/audit-log?limit=100000")).status_code == 422


async def test_audit_log_is_admin_only(client, alice, test_engine):
    await _create_user(test_engine, "bob@example.com", "Bob")
    await _login(client, "bob@example.com")
    assert (await client.get("/api/admin/audit-log")).status_code == 403


async def test_audit_log_requires_login(client):
    assert (await client.get("/api/admin/audit-log")).status_code == 401


async def test_audit_log_keeps_entries_for_a_deleted_account(client, alice, test_engine):
    bob = await _create_user(test_engine, "bob@example.com", "Bob")
    await _login(client, "alice@example.com")
    await client.post(f"/api/admin/users/{bob.id}/revoke-sessions")

    from sqlalchemy import delete
    from sqlalchemy.ext.asyncio import async_sessionmaker

    from app.models.user import User

    maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with maker() as session:
        await session.execute(delete(User).where(User.id == bob.id))
        await session.commit()

    [entry] = (await client.get("/api/admin/audit-log")).json()
    assert entry["action"] == "user.sessions_revoked"
    assert entry["target_name"] is None  # (the FK itself is SET NULL by Postgres, not by SQLite)
