from __future__ import annotations

import io
import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.jwt import create_access_token
from app.auth.password import hash_password
from app.models.user import UserRole
from app.repositories.user import UserRepository


@pytest.fixture(scope="function")
async def owner(db_session: AsyncSession):
    """Create a test user (owner) and return (user_id, auth_token)."""
    repo = UserRepository(db_session)
    user = await repo.create(
        email=f"owner_{uuid.uuid4().hex[:8]}@test.com",
        password_hash=hash_password("securePassword123"),
        full_name="Test Owner",
    )
    token = create_access_token(user.id, UserRole.USER.value)
    return user.id, token


@pytest.fixture(scope="function")
async def collab(db_session: AsyncSession):
    """Create a second test user (collaborator) and return (user_id, auth_token)."""
    repo = UserRepository(db_session)
    user = await repo.create(
        email=f"collab_{uuid.uuid4().hex[:8]}@test.com",
        password_hash=hash_password("securePassword123"),
        full_name="Test Collaborator",
    )
    token = create_access_token(user.id, UserRole.USER.value)
    return user.id, token


def auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def upload_file(client: AsyncClient, token: str, name: str = "test.txt",
                       content: bytes = b"hello world", folder_id: str | None = None) -> dict:
    qs = f"?folder_id={folder_id}" if folder_id else ""
    resp = await client.post(
        f"/api/v1/files/upload{qs}",
        files={"file": (name, io.BytesIO(content), "text/plain")},
        headers=auth(token),
    )
    assert resp.status_code == 201
    return resp.json()


async def create_folder(client: AsyncClient, token: str, name: str,
                         parent_id: str | None = None) -> dict:
    body = {"name": name}
    if parent_id:
        body["parent_id"] = parent_id
    resp = await client.post("/api/v1/folders", json=body, headers=auth(token))
    assert resp.status_code == 201
    return resp.json()
