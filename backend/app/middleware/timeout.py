from __future__ import annotations

import asyncio

from starlette.types import ASGIApp, Receive, Scope, Send

from app.config.settings import settings
from app.core.logging_config import get_logger

logger = get_logger(__name__)


class RequestTimeoutMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app
        self._timeout = settings.REQUEST_TIMEOUT_SECONDS

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        try:
            await asyncio.wait_for(
                self.app(scope, receive, send),
                timeout=self._timeout,
            )
        except TimeoutError:
            logger.warning(
                "request_timeout",
                method=scope.get("method", "UNKNOWN"),
                path=scope.get("path", "/"),
                timeout=self._timeout,
            )
