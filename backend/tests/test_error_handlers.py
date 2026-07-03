from __future__ import annotations

import pytest
from fastapi import Request
from httpx import AsyncClient

from app.core.error_handlers import unhandled_exception_handler


@pytest.mark.asyncio
async def test_not_found_returns_standard_error(client: AsyncClient):
    response = await client.get("/api/v1/nonexistent-endpoint")
    assert response.status_code == 404
    body = response.json()
    assert body["success"] is False
    assert body["code"] == "NOT_FOUND"
    assert "trace_id" in body


@pytest.mark.asyncio
async def test_method_not_allowed_returns_standard_error(client: AsyncClient):
    response = await client.post("/api/v1/health")
    assert response.status_code == 405
    body = response.json()
    assert body["success"] is False
    assert "trace_id" in body


@pytest.mark.asyncio
async def test_unhandled_exception_handler_response():
    request = Request(scope={
        "type": "http",
        "method": "GET",
        "path": "/test",
        "headers": [],
        "query_string": b"",
        "server": ("testserver", 80),
        "client": ("127.0.0.1", 12345),
    })
    request.state.trace_id = "test-trace-id"

    exc = ValueError("simulated unhandled error")

    response = await unhandled_exception_handler(request, exc)
    assert response.status_code == 500
    body = response.body.decode()
    import json
    data = json.loads(body)
    assert data["success"] is False
    assert data["code"] == "INTERNAL_ERROR"
    assert "An unexpected error occurred" in data["message"]
    assert data["trace_id"] == "test-trace-id"
