from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.cli import create_superuser
from app.models.user import User


async def test_create_superuser_creates_active_superuser(test_engine, monkeypatch):
    import app.db as db_module

    monkeypatch.setattr(db_module, "_get_engine_and_sessionmaker", lambda: (test_engine, async_sessionmaker(test_engine, expire_on_commit=False)))

    await create_superuser("admin@example.com", "correcthorsebatterystaple", "Admin")

    maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with maker() as session:
        result = await session.execute(select(User).where(User.email == "admin@example.com"))
        user = result.scalar_one()
        assert user.is_superuser is True
        assert user.is_active is True
        assert user.display_name == "Admin"


async def test_create_superuser_rejects_duplicate_email(test_engine, monkeypatch, capsys):
    import app.db as db_module

    monkeypatch.setattr(db_module, "_get_engine_and_sessionmaker", lambda: (test_engine, async_sessionmaker(test_engine, expire_on_commit=False)))

    await create_superuser("admin@example.com", "correcthorsebatterystaple", "Admin")
    await create_superuser("admin@example.com", "correcthorsebatterystaple", "Admin")

    maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with maker() as session:
        result = await session.execute(select(User).where(User.email == "admin@example.com"))
        assert len(list(result.scalars())) == 1
