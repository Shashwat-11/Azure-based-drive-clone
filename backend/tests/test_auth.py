from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.jwt import create_access_token, create_refresh_token, decode_token
from app.auth.password import hash_password
from app.models.user import UserRole
from app.repositories.user import RefreshTokenRepository, UserRepository

TEST_EMAIL = "test@example.com"
TEST_PASSWORD = "securePassword123"
TEST_FULL_NAME = "Test User"


async def _create_test_user(db: AsyncSession) -> uuid.UUID:
    repo = UserRepository(db)
    user = await repo.create(
        email=TEST_EMAIL,
        password_hash=hash_password(TEST_PASSWORD),
        full_name=TEST_FULL_NAME,
    )
    return user.id


class TestRegister:
    @pytest.mark.asyncio
    async def test_register_creates_user(self, client: AsyncClient):
        response = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "newuser@example.com",
                "password": "securePassword123",
                "full_name": "New User",
            },
        )
        assert response.status_code == 201
        body = response.json()
        assert body["email"] == "newuser@example.com"
        assert body["full_name"] == "New User"
        assert body["role"] == "user"
        assert "id" in body
        assert "password" not in body
        assert "password_hash" not in body

    @pytest.mark.asyncio
    async def test_register_duplicate_email_fails(self, client: AsyncClient):
        response = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "dupe@example.com",
                "password": "securePassword123",
                "full_name": "First User",
            },
        )
        assert response.status_code == 201

        response = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "dupe@example.com",
                "password": "otherPassword456",
                "full_name": "Second User",
            },
        )
        assert response.status_code == 409
        body = response.json()
        assert body["success"] is False
        assert body["code"] == "CONFLICT"

    @pytest.mark.asyncio
    async def test_register_short_password_fails(self, client: AsyncClient):
        response = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "weak@example.com",
                "password": "short",
                "full_name": "Weak User",
            },
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_register_invalid_email_fails(self, client: AsyncClient):
        response = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "not-an-email",
                "password": "securePassword123",
                "full_name": "Bad Email User",
            },
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_register_empty_name_fails(self, client: AsyncClient):
        response = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "noname@example.com",
                "password": "securePassword123",
                "full_name": "",
            },
        )
        assert response.status_code == 422


class TestLogin:
    @pytest.mark.asyncio
    async def test_login_success_returns_tokens(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        user_id = await _create_test_user(db_session)

        response = await client.post(
            "/api/v1/auth/login",
            json={
                "email": TEST_EMAIL,
                "password": TEST_PASSWORD,
            },
        )
        assert response.status_code == 200
        body = response.json()
        assert "access_token" in body
        assert "refresh_token" in body
        assert body["token_type"] == "bearer"

        payload = decode_token(body["access_token"])
        assert payload["sub"] == str(user_id)
        assert payload["type"] == "access"

    @pytest.mark.asyncio
    async def test_login_wrong_password_fails(self, client: AsyncClient, db_session: AsyncSession):
        await _create_test_user(db_session)

        response = await client.post(
            "/api/v1/auth/login",
            json={
                "email": TEST_EMAIL,
                "password": "wrongPassword",
            },
        )
        assert response.status_code == 401
        body = response.json()
        assert body["code"] == "AUTHENTICATION_REQUIRED"

    @pytest.mark.asyncio
    async def test_login_nonexistent_user_fails(self, client: AsyncClient):
        response = await client.post(
            "/api/v1/auth/login",
            json={
                "email": "nonexistent@example.com",
                "password": "anyPassword",
            },
        )
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_login_inactive_user_fails(self, client: AsyncClient, db_session: AsyncSession):
        user_id = await _create_test_user(db_session)
        repo = UserRepository(db_session)
        user = await repo.get_by_id(user_id)
        user.is_active = False
        await repo.update(user)

        response = await client.post(
            "/api/v1/auth/login",
            json={
                "email": TEST_EMAIL,
                "password": TEST_PASSWORD,
            },
        )
        assert response.status_code == 401


class TestRefreshToken:
    @pytest.mark.asyncio
    async def test_refresh_returns_new_tokens(self, client: AsyncClient, db_session: AsyncSession):
        user_id = await _create_test_user(db_session)
        refresh_token = create_refresh_token(user_id)

        from datetime import UTC, datetime, timedelta

        token_repo = RefreshTokenRepository(db_session)
        await token_repo.create(
            user_id, refresh_token, datetime.now(UTC) + timedelta(days=7)
        )

        response = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": refresh_token},
        )
        assert response.status_code == 200
        body = response.json()
        assert "access_token" in body
        assert "refresh_token" in body
        assert body["refresh_token"] != refresh_token

    @pytest.mark.asyncio
    async def test_refresh_invalid_token_fails(self, client: AsyncClient):
        response = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": "invalid-token"},
        )
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_refresh_expired_token_fails(self, client: AsyncClient, db_session: AsyncSession):
        user_id = await _create_test_user(db_session)
        refresh_token = create_refresh_token(user_id)

        from datetime import UTC, datetime, timedelta

        token_repo = RefreshTokenRepository(db_session)
        await token_repo.create(
            user_id, refresh_token, datetime.now(UTC) - timedelta(days=1)
        )

        response = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": refresh_token},
        )
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_double_refresh_fails(self, client: AsyncClient, db_session: AsyncSession):
        user_id = await _create_test_user(db_session)
        refresh_token = create_refresh_token(user_id)

        from datetime import UTC, datetime, timedelta

        token_repo = RefreshTokenRepository(db_session)
        await token_repo.create(
            user_id, refresh_token, datetime.now(UTC) + timedelta(days=7)
        )

        response = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": refresh_token},
        )
        assert response.status_code == 200

        response = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": refresh_token},
        )
        assert response.status_code == 401


class TestMe:
    @pytest.mark.asyncio
    async def test_me_returns_current_user(self, client: AsyncClient, db_session: AsyncSession):
        user_id = await _create_test_user(db_session)
        access_token = create_access_token(user_id, UserRole.USER.value)

        response = await client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["email"] == TEST_EMAIL
        assert body["id"] == str(user_id)
        assert body["role"] == "user"

    @pytest.mark.asyncio
    async def test_me_without_token_fails(self, client: AsyncClient):
        response = await client.get("/api/v1/auth/me")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_me_with_invalid_token_fails(self, client: AsyncClient):
        response = await client.get(
            "/api/v1/auth/me",
            headers={"Authorization": "Bearer invalid-token"},
        )
        assert response.status_code == 401


class TestLogout:
    @pytest.mark.asyncio
    async def test_logout_revokes_token(self, client: AsyncClient, db_session: AsyncSession):
        user_id = await _create_test_user(db_session)
        refresh_token = create_refresh_token(user_id)

        from datetime import UTC, datetime, timedelta

        token_repo = RefreshTokenRepository(db_session)
        await token_repo.create(
            user_id, refresh_token, datetime.now(UTC) + timedelta(days=7)
        )

        response = await client.post(
            "/api/v1/auth/logout",
            json={"refresh_token": refresh_token},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True

        rt = await token_repo.get_by_token(refresh_token)
        assert rt is not None
        assert rt.is_revoked is True


class TestRBAC:
    @pytest.mark.asyncio
    async def test_admin_only_allows_admin(self, client: AsyncClient, db_session: AsyncSession):
        user = await UserRepository(db_session).create(
            email="admin@example.com",
            password_hash=hash_password("adminPass123"),
            full_name="Admin User",
            role=UserRole.ADMIN,
        )
        access_token = create_access_token(user.id, UserRole.ADMIN.value)

        response = await client.get(
            "/api/v1/auth/admin-only",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        assert body["code"] == "ADMIN_ACCESS"

    @pytest.mark.asyncio
    async def test_admin_only_rejects_user_role(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        user_id = await _create_test_user(db_session)
        access_token = create_access_token(user_id, UserRole.USER.value)

        response = await client.get(
            "/api/v1/auth/admin-only",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert response.status_code == 403
        body = response.json()
        assert body["code"] == "FORBIDDEN"

    @pytest.mark.asyncio
    async def test_admin_only_rejects_viewer_role(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        user = await UserRepository(db_session).create(
            email="viewer@example.com",
            password_hash=hash_password("viewerPass123"),
            full_name="Viewer User",
            role=UserRole.VIEWER,
        )
        access_token = create_access_token(user.id, UserRole.VIEWER.value)

        response = await client.get(
            "/api/v1/auth/admin-only",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert response.status_code == 403
