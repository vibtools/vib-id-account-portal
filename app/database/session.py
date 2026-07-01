"""Async database engine and request-scoped session factory."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.config import Settings


class Database:
    def __init__(self, settings: Settings) -> None:
        engine_kwargs: dict[str, object] = {
            "pool_pre_ping": True,
            "echo": settings.APP_ENV == "development" and settings.LOG_LEVEL == "DEBUG",
        }
        if settings.DATABASE_URL.startswith("postgresql"):
            engine_kwargs.update(
                pool_size=settings.DATABASE_POOL_SIZE,
                max_overflow=settings.DATABASE_MAX_OVERFLOW,
                pool_timeout=settings.DATABASE_POOL_TIMEOUT,
            )
        self.engine: AsyncEngine = create_async_engine(settings.DATABASE_URL, **engine_kwargs)
        self.session_factory = async_sessionmaker(
            self.engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=False,
        )

    @asynccontextmanager
    async def session(self) -> AsyncIterator[AsyncSession]:
        async with self.session_factory() as session:
            try:
                yield session
            except Exception:
                await session.rollback()
                raise
            finally:
                await session.close()

    async def dispose(self) -> None:
        await self.engine.dispose()
