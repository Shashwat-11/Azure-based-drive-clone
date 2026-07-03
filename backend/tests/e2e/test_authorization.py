from __future__ import annotations

import pytest
from httpx import AsyncClient

from tests.e2e.conftest import auth, upload_file


class TestAuthorizationE2E:
    @pytest.mark.asyncio
    async def test_unauthorized_endpoints_return_401(self, client: AsyncClient):
        endpoints = [
            ("GET", "/api/v1/auth/me"),
            ("GET", "/api/v1/files"),
            ("POST", "/api/v1/folders", {"name": "test"}),
            ("GET", "/api/v1/search"),
            ("GET", "/api/v1/favorites"),
            ("GET", "/api/v1/recent"),
            ("GET", "/api/v1/tags"),
        ]
        for method, path, *body in endpoints:
            if method == "GET":
                resp = await client.get(path)
            else:
                resp = await client.post(path, json=body[0] if body else {})
            assert resp.status_code == 401, f"{method} {path} should return 401"

    @pytest.mark.asyncio
    async def test_cross_user_access_returns_404(self, client: AsyncClient, owner, collab):
        _, token1 = owner
        _, token2 = collab

        f = await upload_file(client, token1, name="private.txt")

        # User2 should not be able to access user1's private file
        resp = await client.get(f"/api/v1/files/{f['id']}", headers=auth(token2))
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_invalid_token_returns_401(self, client: AsyncClient):
        resp = await client.get("/api/v1/auth/me", headers=auth("invalid-token"))
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_missing_auth_header(self, client: AsyncClient, owner):
        _, token = owner
        f = await upload_file(client, token, name="hidden.txt")

        resp = await client.get(f"/api/v1/files/{f['id']}")
        assert resp.status_code == 401
