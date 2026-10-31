import json

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.models.audit import AuditLog
from app.services.audit import log_audit


async def test_log_audit_records_actor_target_action_and_detail(test_engine, alice):
    maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with maker() as session:
        await log_audit(session, alice, "user.deactivated", alice, reason="left the house")
        await session.commit()

    async with maker() as session:
        entry = (await session.execute(select(AuditLog))).scalar_one()

    assert entry.actor_id == alice.id
    assert entry.target_user_id == alice.id
    assert entry.action == "user.deactivated"
    assert json.loads(entry.detail) == {"reason": "left the house"}
    assert entry.created_at is not None


async def test_log_audit_without_target_or_detail(test_engine, alice):
    maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with maker() as session:
        await log_audit(session, alice, "something.happened")
        await session.commit()

    async with maker() as session:
        entry = (await session.execute(select(AuditLog))).scalar_one()

    assert entry.target_user_id is None
    assert entry.detail is None


async def test_log_audit_does_not_commit_on_its_own(test_engine, alice):
    """The entry must land in the caller's transaction, so a failed admin action rolls the
    audit row back with it instead of leaving a record of something that never happened.
    """
    maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with maker() as session:
        await log_audit(session, alice, "user.deactivated", alice)
        await session.rollback()

    async with maker() as session:
        assert (await session.execute(select(AuditLog))).first() is None
