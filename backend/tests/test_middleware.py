from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_correlation_id_header_present(client: AsyncClient):
    response = await client.get("/api/v1/health")
    assert "X-Request-ID" in response.headers
    assert "X-Trace-ID" in response.headers
    request_id = response.headers["X-Request-ID"]
    assert len(request_id) == 36  # UUID format


@pytest.mark.asyncio
async def test_correlation_id_header_forwarded(client: AsyncClient):
    response = await client.get(
        "/api/v1/health",
        headers={"X-Request-ID": "custom-request-id-12345"},
    )
    assert response.headers["X-Request-ID"] == "custom-request-id-12345"
    assert response.headers["X-Trace-ID"] == "custom-request-id-12345"


@pytest.mark.asyncio
async def test_correlation_id_custom_header_case_insensitive(client: AsyncClient):
    response = await client.get(
        "/api/v1/health",
        headers={"x-request-id": "lowercase-id-67890"},
    )
    assert response.headers["X-Request-ID"] == "lowercase-id-67890"


@pytest.mark.asyncio
async def test_correlation_id_unique_per_request(client: AsyncClient):
    response1 = await client.get("/api/v1/health")
    response2 = await client.get("/api/v1/health")
    id1 = response1.headers["X-Request-ID"]
    id2 = response2.headers["X-Request-ID"]
    assert id1 != id2
