import pytest_asyncio
from fastapi_users.db import SQLAlchemyUserDatabase
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app import models  # noqa: F401  (registers all tables on Base.metadata)
from app.auth.users import UserManager
from app.db import Base, get_session
from app.main import app
from app.models.user import User
from app.schemas.user import UserCreate


@pytest_asyncio.fixture
async def test_engine():
    # StaticPool keeps a single SQLite connection alive for the whole test so an in-memory
    # database isn't silently recreated empty on the next connection.
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def client(test_engine):
    maker = async_sessionmaker(test_engine, expire_on_commit=False)

    async def override_get_session():
        async with maker() as session:
            yield session

    app.dependency_overrides[get_session] = override_get_session
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def alice(test_engine) -> User:
    maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with maker() as session:
        manager = UserManager(SQLAlchemyUserDatabase(session, User))
        return await manager.create(
            UserCreate(
                email="alice@example.com",
                password="correcthorsebatterystaple",
                display_name="Alice",
                is_superuser=True,
            ),
            safe=False,
        )
