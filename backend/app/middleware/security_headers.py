from __future__ import annotations

from starlette.types import ASGIApp, Receive, Scope, Send

from app.config.settings import settings


class SecurityHeadersMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def send_wrapper(message: dict) -> None:
            if message["type"] == "http.response.start" and settings.SECURE_HEADERS_ENABLED:
                existing_headers: list[tuple[bytes, bytes]] = list(message.get("headers", []))
                existing_headers.append((b"x-content-type-options", b"nosniff"))
                existing_headers.append((b"x-frame-options", b"DENY"))
                existing_headers.append((b"x-xss-protection", b"1; mode=block"))
                existing_headers.append((b"referrer-policy", b"strict-origin-when-cross-origin"))
                existing_headers.append(
                    (b"permissions-policy", b"geolocation=(), microphone=(), camera=()")
                )
                existing_headers.append((b"cache-control", b"no-store, max-age=0"))
                if scope.get("scheme") == "https":
                    existing_headers.append(
                        (b"strict-transport-security", b"max-age=31536000; includeSubDomains")
                    )
                message["headers"] = existing_headers
            await send(message)

        await self.app(scope, receive, send_wrapper)
