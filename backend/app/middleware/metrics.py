from __future__ import annotations

import time
from collections import defaultdict

from starlette.types import ASGIApp, Receive, Scope, Send

from app.config.settings import settings
from app.core.logging_config import get_logger

logger = get_logger(__name__)

_request_count: defaultdict[str, int] = defaultdict(int)
_request_duration_sum: defaultdict[str, float] = defaultdict(float)
_request_duration_buckets: defaultdict[str, list[float]] = defaultdict(list)

_BUCKET_BOUNDARIES = [0.01, 0.05, 0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0]


class MetricsMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or not settings.METRICS_ENABLED:
            await self.app(scope, receive, send)
            return

        start = time.monotonic()
        method = scope.get("method", "UNKNOWN")
        path = scope.get("path", "/")
        status_code = 500

        async def send_wrapper(message):
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            duration = time.monotonic() - start
            label = f"{method} {path}"
            _request_count[label] += 1
            _request_duration_sum[label] += duration
            _request_duration_buckets[label].append(duration)
            self._record_bucket(label, duration)

    @staticmethod
    def _record_bucket(label: str, duration: float) -> None:
        if len(_request_duration_buckets[label]) > 10000:
            _request_duration_buckets[label] = _request_duration_buckets[label][-5000:]


def get_metrics_text() -> str:
    lines = []
    for label, count in sorted(_request_count.items()):
        safe = label.replace('"', '\\"')
        lines.append(f'http_requests_total{{endpoint="{safe}"}} {count}')
    for label, total_dur in sorted(_request_duration_sum.items()):
        safe = label.replace('"', '\\"')
        count = _request_count.get(label, 1)
        lines.append(f'http_request_duration_seconds_sum{{endpoint="{safe}"}} {total_dur:.6f}')
        lines.append(f'http_request_duration_seconds_count{{endpoint="{safe}"}} {count}')
        if count > 0:
            lines.append(f'http_request_duration_seconds_avg{{endpoint="{safe}"}} {total_dur / count:.6f}')
    lines.append(f'http_requests_in_flight_total {len(_request_duration_buckets)}')
    lines.append("")
    return "\n".join(lines)
