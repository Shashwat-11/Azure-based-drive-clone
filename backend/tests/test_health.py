from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health_check(client: AsyncClient):
    response = await client.get("/api/v1/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "healthy"


@pytest.mark.asyncio
async def test_liveness_check(client: AsyncClient):
    response = await client.get("/api/v1/live")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "alive"


@pytest.mark.asyncio
async def test_startup_check(client: AsyncClient):
    response = await client.get("/api/v1/startup")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "started"


@pytest.mark.asyncio
async def test_readiness_check_returns_checks(client: AsyncClient):
    response = await client.get("/api/v1/ready")
    assert response.status_code == 200
    body = response.json()
    assert "checks" in body
    assert "database" in body["checks"]
    assert "redis" in body["checks"]
    assert "storage" in body["checks"]


@pytest.mark.asyncio
async def test_readiness_database_healthy(client: AsyncClient):
    response = await client.get("/api/v1/ready")
    body = response.json()
    assert body["checks"]["database"]["status"] == "healthy"


@pytest.mark.asyncio
async def test_metrics_endpoint(client: AsyncClient):
    response = await client.get("/metrics")
    assert response.status_code == 200
    assert "http_requests_total" in response.text
