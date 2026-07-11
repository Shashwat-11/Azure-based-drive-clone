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
        logger.debug("get_redis_creating_client", host=settings.REDIS_HOST, port=settings.REDIS_PORT)
        _redis_client = aioredis.from_url(
            settings.REDIS_URL,
            max_connections=settings.REDIS_POOL_SIZE,
            decode_responses=True,
            socket_connect_timeout=5,
            socket_keepalive=True,
        )
        logger.info(
            "redis_client_created_lazy_connection",
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            db=settings.REDIS_DB,
            url_scheme=settings.REDIS_URL.split("://")[0] if "://" in settings.REDIS_URL else "unknown",
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
