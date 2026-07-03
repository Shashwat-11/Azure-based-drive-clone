from __future__ import annotations

import asyncio
import random
from collections.abc import Awaitable, Callable
from typing import TypeVar

from app.core.logging_config import get_logger

logger = get_logger(__name__)

T = TypeVar("T")


async def with_retry[T](
    fn: Callable[[], Awaitable[T]],
    *,
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 30.0,
    jitter: bool = True,
) -> T:
    last_exception = None
    for attempt in range(max_retries + 1):
        try:
            return await fn()
        except Exception as exc:
            last_exception = exc
            if attempt < max_retries:
                delay = min(base_delay * (2 ** attempt), max_delay)
                if jitter:
                    delay *= 0.5 + random.random()
                logger.warning(
                    "retry_attempt",
                    attempt=attempt + 1,
                    max_retries=max_retries,
                    delay=round(delay, 2),
                    error=str(exc),
                )
                await asyncio.sleep(delay)
    raise last_exception  # type: ignore[misc]
