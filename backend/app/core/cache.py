from __future__ import annotations

import json
from collections.abc import Awaitable, Callable
from typing import TypeVar

from app.core.logging_config import get_logger

logger = get_logger(__name__)

T = TypeVar("T")

DEFAULT_TTL = 300
SHORT_TTL = 60
LONG_TTL = 3600


def _cache_key(prefix: str, *parts: str) -> str:
    return f"cache:{prefix}:{':'.join(parts)}"


async def cached(
    prefix: str,
    key_parts: list[str],
    ttl: int = DEFAULT_TTL,
) -> Callable[[Callable[[], Awaitable[T]]], Awaitable[T]]:
    """Decorator-like factory: try Redis, fallback to fn, cache result."""
    async def wrapper(fn: Callable[[], Awaitable[T]]) -> T:
        cache_key = _cache_key(prefix, *key_parts)
        try:
            from app.dependencies.redis import get_redis
            redis_client = await get_redis()
            cached_value = await redis_client.get(cache_key)
            if cached_value is not None:
                return json.loads(cached_value)
        except Exception:
            pass

        result = await fn()

        try:
            from app.dependencies.redis import get_redis
            redis_client = await get_redis()
            await redis_client.setex(cache_key, ttl, json.dumps(result, default=str))
        except Exception as exc:
            logger.debug("cache_write_failed", key=cache_key, error=str(exc))

        return result

    return wrapper


async def invalidate(prefix: str, *key_parts: str) -> None:
    try:
        from app.dependencies.redis import get_redis
        redis_client = await get_redis()
        cache_key = _cache_key(prefix, *key_parts)
        await redis_client.delete(cache_key)
    except Exception as exc:
        logger.debug("cache_invalidate_failed", key=prefix, error=str(exc))
