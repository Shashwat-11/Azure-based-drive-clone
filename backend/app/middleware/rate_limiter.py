from __future__ import annotations

from starlette.types import ASGIApp, Receive, Scope, Send

from app.config.settings import settings
from app.core.logging_config import get_logger
from app.dependencies.redis import get_redis

logger = get_logger(__name__)


class RateLimiterMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        if not settings.RATE_LIMIT_ENABLED:
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "/")
        protected_paths = (
            "/api/v1/auth/login",
            "/api/v1/auth/register",
            "/api/v1/collaboration/links/access",
        )
        if not any(path.startswith(p) for p in protected_paths):
            await self.app(scope, receive, send)
            return

        client_ip = "unknown"
        if scope.get("client"):
            client_ip = scope["client"][0]

        key = f"rate_limit:{client_ip}:{path}"

        try:
            redis_client = await get_redis()
            current_count = await redis_client.incr(key)
            if current_count == 1:
                await redis_client.expire(key, settings.RATE_LIMIT_WINDOW_SECONDS)

            limit = settings.RATE_LIMIT_REQUESTS
            if current_count > limit:
                ttl = await redis_client.ttl(key)
                logger.warning(
                    "rate_limit_exceeded",
                    client_ip=client_ip,
                    path=path,
                    count=current_count,
                    limit=limit,
                )
                await self._send_rate_limit_response(send, ttl)
                return

            await self.app(scope, receive, send)

        except Exception as exc:
            logger.warning(
                "rate_limiter_bypassed",
                client_ip=client_ip,
                path=path,
                error=str(exc),
            )
            await self.app(scope, receive, send)

    async def _send_rate_limit_response(self, send: Send, retry_after: int) -> None:
        import json

        body = json.dumps({
            "success": False,
            "message": "Too many requests",
            "code": "RATE_LIMIT_EXCEEDED",
        }).encode()

        await send({
            "type": "http.response.start",
            "status": 429,
            "headers": [
                (b"content-type", b"application/json"),
                (b"retry-after", str(retry_after).encode()),
            ],
        })
        await send({
            "type": "http.response.body",
            "body": body,
        })
