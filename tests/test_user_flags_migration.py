import asyncio
import os
import uuid

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.config import get_settings
from app.models.user import User

# The head before user deactivation / passwordless flags were added.
PREVIOUS_HEAD = "d9e5b2c7f4a8"

# The existing migrations use Postgres-only SQL (e.g. ALTER COLUMN ... DROP NOT NULL), so the
# migration tests can't run on the SQLite the rest of the suite uses. Point this at a scratch
# Postgres database (it gets wiped) to run them; CI sets it from a service container.
MIGRATION_DB_URL = os.environ.get("MIGRATION_TEST_DATABASE_URL")


async def test_new_user_defaults_to_password_login_and_not_deactivated(test_engine, alice):
    maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with maker() as session:
        user = (await session.execute(select(User).where(User.id == alice.id))).scalar_one()
    assert user.password_login_enabled is True
    assert user.deactivated_at is None


requires_postgres = pytest.mark.skipif(
    not MIGRATION_DB_URL, reason="set MIGRATION_TEST_DATABASE_URL to a scratch Postgres database"
)


@pytest.fixture
def migration_db(monkeypatch):
    # env.py reads the URL from Settings, which is cached — point it at the scratch database
    # and start from an empty schema.
    monkeypatch.setenv("DATABASE_URL", MIGRATION_DB_URL)
    get_settings.cache_clear()
    _reset_schema()
    yield Config("alembic.ini")
    _reset_schema()
    get_settings.cache_clear()


def _reset_schema() -> None:
    # Wipe rather than `alembic downgrade base`: the first revisions' downgrades can't run
    # (they drop unnamed constraints), and only the newest revision's downgrade matters here.
    _run_sql([("DROP SCHEMA public CASCADE", {}), ("CREATE SCHEMA public", {})])


def _run_sql(statements: list[tuple[str, dict]]) -> list:
    async def go():
        engine = create_async_engine(MIGRATION_DB_URL)
        rows = []
        async with engine.begin() as conn:
            for sql, params in statements:
                result = await conn.execute(text(sql), params)
                if result.returns_rows:
                    rows.extend(result.fetchall())
        await engine.dispose()
        return rows

    return asyncio.run(go())


@requires_postgres
def test_upgrade_keeps_existing_users_logins_intact(migration_db):
    command.upgrade(migration_db, PREVIOUS_HEAD)

    user_id = uuid.uuid4()
    _run_sql(
        [
            (
                'INSERT INTO "user" (id, email, hashed_password, is_active, is_superuser, is_verified, '
                "display_name, is_2fa_enabled, totp_secret, totp_recovery_codes, totp_failed_attempts, "
                "calendar_feed_token) VALUES (:id, 'old@example.com', '$argon2$old-hash', true, false, "
                "false, 'Old', true, 'TOTPSECRET', '[\"code-hash\"]', 0, 'feed-token')",
                {"id": user_id},
            ),
            (
                "INSERT INTO device_trust (id, user_id, device_id, pin_hash, failed_pin_attempts) "
                "VALUES (:id, :user_id, 'device-1', 'pin-hash', 0)",
                {"id": uuid.uuid4(), "user_id": user_id},
            ),
        ]
    )

    command.upgrade(migration_db, "head")

    [row] = _run_sql(
        [
            (
                'SELECT hashed_password, is_active, is_2fa_enabled, totp_secret, totp_recovery_codes, '
                'password_login_enabled, deactivated_at FROM "user" WHERE id = :id',
                {"id": user_id},
            )
        ]
    )
    [device] = _run_sql([("SELECT pin_hash FROM device_trust WHERE user_id = :id", {"id": user_id})])

    # Credentials are untouched...
    assert tuple(row[:5]) == ("$argon2$old-hash", True, True, "TOTPSECRET", '["code-hash"]')
    assert device[0] == "pin-hash"
    # ...and the new columns come up with safe defaults, so nobody has to reset anything.
    assert row[5] is True
    assert row[6] is None


@requires_postgres
def test_downgrade_removes_the_new_columns(migration_db):
    def user_columns() -> set[str]:
        rows = _run_sql(
            [("SELECT column_name FROM information_schema.columns WHERE table_name = 'user'", {})]
        )
        return {r[0] for r in rows}

    command.upgrade(migration_db, "head")
    assert {"password_login_enabled", "deactivated_at"} <= user_columns()

    command.downgrade(migration_db, PREVIOUS_HEAD)
    columns = user_columns()
    assert "password_login_enabled" not in columns
    assert "deactivated_at" not in columns


@requires_postgres
def test_audit_log_table_is_created_and_dropped(migration_db):
    def has_audit_log() -> bool:
        rows = _run_sql([("SELECT to_regclass('public.audit_log')", {})])
        return rows[0][0] is not None

    command.upgrade(migration_db, "head")
    assert has_audit_log()

    command.downgrade(migration_db, "a2c6e8f1b3d5")
    assert not has_audit_log()


@requires_postgres
def test_oauth_account_table_is_created_and_dropped(migration_db):
    def has_oauth_account() -> bool:
        rows = _run_sql([("SELECT to_regclass('public.oauth_account')", {})])
        return rows[0][0] is not None

    command.upgrade(migration_db, "head")
    assert has_oauth_account()

    command.downgrade(migration_db, "b3d7f9a2c4e6")
    assert not has_oauth_account()
