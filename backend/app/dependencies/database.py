from __future__ import annotations

from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.config.settings import settings
from app.core.logging_config import get_logger

logger = get_logger(__name__)

_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def get_engine() -> AsyncEngine:
    global _engine
    if _engine is None:
        logger.debug("get_engine_creating", host=settings.DB_HOST, port=settings.DB_PORT)
        _engine = create_async_engine(
            settings.DATABASE_URL,
            pool_size=settings.DB_POOL_SIZE,
            max_overflow=settings.DB_POOL_OVERFLOW,
            pool_timeout=settings.DB_POOL_TIMEOUT,
            echo=settings.DB_ECHO,
            pool_pre_ping=True,
            connect_args={"timeout": 10, "command_timeout": 30},
        )
        logger.info(
            "database_engine_created",
            pool_size=settings.DB_POOL_SIZE,
            max_overflow=settings.DB_POOL_OVERFLOW,
        )
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(
            bind=get_engine(),
            class_=AsyncSession,
            expire_on_commit=False,
        )
    return _session_factory


async def get_db() -> AsyncIterator[AsyncSession]:
    logger.debug("get_db_enter")
    factory = get_session_factory()
    logger.debug("get_db_session_factory_obtained")
    async with factory() as session:
        try:
            t0 = __import__("time").monotonic()
            logger.debug("get_db_yielding_session")
            yield session
            dt = round((__import__("time").monotonic() - t0) * 1000)
            logger.debug("get_db_session_returned", duration_ms=dt)
            if session.is_modified:
                logger.debug("get_db_committing")
                await session.commit()
                logger.debug("get_db_committed")
        except Exception:
            logger.debug("get_db_rolling_back")
            await session.rollback()
            raise


async def close_db() -> None:
    global _engine, _session_factory
    if _engine is not None:
        await _engine.dispose()
        _engine = None
        _session_factory = None
        logger.info("database_engine_disposed")
