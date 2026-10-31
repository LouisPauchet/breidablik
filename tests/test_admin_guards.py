import pytest
from fastapi import HTTPException
from fastapi_users.db import SQLAlchemyUserDatabase
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.auth.users import UserManager
from app.models.user import User
from app.schemas.user import UserCreate
from app.services.admin_guards import assert_not_last_admin, assert_not_self


async def _make_user(session, email: str, **kwargs) -> User:
    manager = UserManager(SQLAlchemyUserDatabase(session, User))
    return await manager.create(
        UserCreate(email=email, password="correcthorsebatterystaple", display_name=email.split("@")[0], **kwargs),
        safe=False,
    )


def test_assert_not_self_rejects_acting_on_yourself(alice):
    with pytest.raises(HTTPException) as exc:
        assert_not_self(alice, alice)
    assert exc.value.status_code == 400
    assert exc.value.detail == "CANNOT_ACT_ON_SELF"


async def test_assert_not_self_allows_other_users(test_engine, alice):
    maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with maker() as session:
        bob = await _make_user(session, "bob@example.com")
    assert_not_self(alice, bob)


async def test_sole_active_admin_cannot_be_removed(test_engine, alice):
    maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with maker() as session:
        with pytest.raises(HTTPException) as exc:
            await assert_not_last_admin(session, alice)
    assert exc.value.status_code == 400
    assert exc.value.detail == "LAST_ADMIN"


async def test_admin_can_be_removed_when_another_active_admin_exists(test_engine, alice):
    maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with maker() as session:
        await _make_user(session, "carol@example.com", is_superuser=True)
        await assert_not_last_admin(session, alice)


async def test_inactive_admins_do_not_count_as_active(test_engine, alice):
    maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with maker() as session:
        # e.g. a pending invite or a deactivated admin: not someone who can run the app.
        await _make_user(session, "dormant@example.com", is_superuser=True, is_active=False)
        with pytest.raises(HTTPException) as exc:
            await assert_not_last_admin(session, alice)
    assert exc.value.detail == "LAST_ADMIN"


async def test_non_admin_target_is_never_blocked(test_engine, alice):
    maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with maker() as session:
        bob = await _make_user(session, "bob@example.com")
        await assert_not_last_admin(session, bob)
