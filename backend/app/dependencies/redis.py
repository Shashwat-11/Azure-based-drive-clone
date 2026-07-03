from __future__ import annotations

from collections.abc import AsyncIterator

import redis.asyncio as aioredis

from app.config.settings import settings
from app.core.logging_config import get_logger

logger = get_logger(__name__)

_redis_client: aioredis.Redis | None = None


async def get_redis() -> aioredis.Redis:
    global _redis_client
    if _redis_client is None:
        _redis_client = aioredis.from_url(
            settings.REDIS_URL,
            max_connections=settings.REDIS_POOL_SIZE,
            decode_responses=True,
        )
        logger.info(
            "redis_connection_established",
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            db=settings.REDIS_DB,
        )
    return _redis_client


async def get_redis_dep() -> AsyncIterator[aioredis.Redis]:
    client = await get_redis()
    yield client


async def close_redis() -> None:
    global _redis_client
    if _redis_client is not None:
        await _redis_client.close()
        _redis_client = None
        logger.info("redis_connection_closed")
