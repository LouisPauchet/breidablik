import asyncio
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from datetime import datetime

from sqlalchemy import DateTime
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import NullPool

from app.config import get_settings


class Base(DeclarativeBase):
    # Every bare `Mapped[datetime]` column is timezone-aware by default. Application code
    # consistently writes datetime.now(timezone.utc); a naive DateTime column would make
    # asyncpg reject those values ("can't subtract offset-naive and offset-aware datetimes").
    type_annotation_map = {datetime: DateTime(timezone=True)}

    pass


# Normal path (Docker, or Passenger running natively as ASGI): one persistent engine bound to
# the single event loop the ASGI server runs on for the life of the process.
_engine: AsyncEngine | None = None
_sessionmaker: async_sessionmaker[AsyncSession] | None = None

# Fallback path, only exercised when PASSENGER_FORCE_WSGI=1: a2wsgi drives the async app from a
# fresh event loop per WSGI call, so a single engine created once at startup would end up bound
# to a stale loop on the next request and raise "Future attached to a different loop". Cache one
# engine per running loop instead, with NullPool so pooled connections are never handed across
# loops either.
_loop_engines: dict[int, tuple[AsyncEngine, async_sessionmaker[AsyncSession]]] = {}


def _build_engine():
    settings = get_settings()
    kwargs = {}
    if settings.passenger_force_wsgi:
        kwargs["poolclass"] = NullPool
    return create_async_engine(settings.database_url, **kwargs)


def _get_engine_and_sessionmaker() -> tuple[AsyncEngine, async_sessionmaker[AsyncSession]]:
    global _engine, _sessionmaker
    settings = get_settings()

    if not settings.passenger_force_wsgi:
        if _engine is None:
            _engine = _build_engine()
            _sessionmaker = async_sessionmaker(_engine, expire_on_commit=False)
        return _engine, _sessionmaker

    loop_id = id(asyncio.get_running_loop())
    cached = _loop_engines.get(loop_id)
    if cached is None:
        engine = _build_engine()
        maker = async_sessionmaker(engine, expire_on_commit=False)
        _loop_engines[loop_id] = (engine, maker)
        return engine, maker
    return cached


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency: one session per request."""
    _, sessionmaker = _get_engine_and_sessionmaker()
    async with sessionmaker() as session:
        yield session


@asynccontextmanager
async def session_scope() -> AsyncGenerator[AsyncSession, None]:
    """For code that runs outside a request (the in-process reminder scheduler, CLI scripts)."""
    _, sessionmaker = _get_engine_and_sessionmaker()
    async with sessionmaker() as session:
        yield session
