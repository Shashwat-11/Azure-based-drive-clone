from __future__ import annotations

import pytest
from httpx import AsyncClient

from tests.e2e.conftest import auth


class TestAuthE2E:
    @pytest.mark.asyncio
    async def test_register_login_me_refresh_logout(self, client: AsyncClient):
        email = f"e2e-auth-{__import__('uuid').uuid4().hex[:8]}@test.com"

        # Register
        reg = await client.post("/api/v1/auth/register", json={
            "email": email, "password": "securePass123", "full_name": "E2E User",
        })
        assert reg.status_code == 201
        assert reg.json()["email"] == email
        assert reg.json()["role"] == "user"

        # Login
        login = await client.post("/api/v1/auth/login", json={
            "email": email, "password": "securePass123",
        })
        assert login.status_code == 200
        tokens = login.json()
        access = tokens["access_token"]
        refresh = tokens["refresh_token"]
        assert len(access) > 0
        assert len(refresh) > 0

        # Me
        me = await client.get("/api/v1/auth/me", headers=auth(access))
        assert me.status_code == 200
        assert me.json()["email"] == email

        # Refresh
        ref = await client.post("/api/v1/auth/refresh", json={"refresh_token": refresh})
        assert ref.status_code == 200
        new_access = ref.json()["access_token"]
        assert len(new_access) > 0

        # Me with new token
        me2 = await client.get("/api/v1/auth/me", headers=auth(new_access))
        assert me2.status_code == 200

        # Logout
        out = await client.post("/api/v1/auth/logout", json={"refresh_token": refresh},
                                headers=auth(access))
        assert out.status_code == 200

    @pytest.mark.asyncio
    async def test_me_without_token_returns_401(self, client: AsyncClient):
        resp = await client.get("/api/v1/auth/me")
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_register_duplicate_rejected(self, client: AsyncClient):
        email = f"dupe-{__import__('uuid').uuid4().hex[:8]}@test.com"
        await client.post("/api/v1/auth/register", json={
            "email": email, "password": "securePass123", "full_name": "First",
        })
        resp = await client.post("/api/v1/auth/register", json={
            "email": email, "password": "securePass123", "full_name": "Second",
        })
        assert resp.status_code == 409

    @pytest.mark.asyncio
    async def test_login_wrong_password(self, client: AsyncClient):
        email = f"wp-{__import__('uuid').uuid4().hex[:8]}@test.com"
        await client.post("/api/v1/auth/register", json={
            "email": email, "password": "rightPass1", "full_name": "User",
        })
        resp = await client.post("/api/v1/auth/login", json={
            "email": email, "password": "wrongPass1",
        })
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_refresh_invalid_token_fails(self, client: AsyncClient):
        resp = await client.post("/api/v1/auth/refresh", json={"refresh_token": "not-a-token"})
        assert resp.status_code == 401
