from __future__ import annotations

import time
import uuid

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.logging_config import get_logger

logger = get_logger(__name__)


class RequestLoggerMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        start_time = time.monotonic()

        headers = {
            k.decode("latin-1"): v.decode("latin-1")
            for k, v in scope.get("headers", [])
        }
        trace_id = headers.get("x-request-id") or str(uuid.uuid4())

        if "state" not in scope:
            scope["state"] = {}
        scope["state"]["trace_id"] = trace_id

        method = scope.get("method", "UNKNOWN")
        path = scope.get("path", "/")

        client_ip = "unknown"
        if scope.get("client"):
            client_ip = scope["client"][0]

        response_status: int = 500

        async def send_wrapper(message: Message) -> None:
            nonlocal response_status
            if message["type"] == "http.response.start":
                response_status = message["status"]
            await send(message)

        logger.info(
            "request_started",
            method=method,
            path=path,
            client_ip=client_ip,
            trace_id=trace_id,
        )

        try:
            await self.app(scope, receive, send_wrapper)
        except Exception:
            response_status = 500
            raise
        finally:
            duration_ms = round((time.monotonic() - start_time) * 1000, 3)
            logger.info(
                "request_completed",
                method=method,
                path=path,
                status_code=response_status,
                duration_ms=duration_ms,
                trace_id=trace_id,
            )
