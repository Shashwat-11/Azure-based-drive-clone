from __future__ import annotations

import uuid

from starlette.types import ASGIApp, Receive, Scope, Send


class CorrelationIdMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers = {k.decode("latin-1"): v.decode("latin-1") for k, v in scope.get("headers", [])}
        trace_id = (
            headers.get("x-request-id")
            or scope.get("state", {}).get("trace_id")
            or str(uuid.uuid4())
        )

        if "state" not in scope:
            scope["state"] = {}
        scope["state"]["trace_id"] = trace_id

        async def send_wrapper(message: dict) -> None:
            if message["type"] == "http.response.start":
                existing_headers: list[tuple[bytes, bytes]] = list(message.get("headers", []))
                existing_headers.append((b"x-request-id", trace_id.encode()))
                existing_headers.append((b"x-trace-id", trace_id.encode()))
                message["headers"] = existing_headers
            await send(message)

        await self.app(scope, receive, send_wrapper)
