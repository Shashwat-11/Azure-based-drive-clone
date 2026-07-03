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


async def _create_user(db: AsyncSession, email: str = "test@example.com") -> tuple[uuid.UUID, str]:
    repo = UserRepository(db)
    user = await repo.create(email=email, password_hash=hash_password("securePassword123"), full_name="Test User")
    token = create_access_token(user.id, UserRole.USER.value)
    return user.id, token


async def _create_second(db: AsyncSession) -> tuple[uuid.UUID, str]:
    return await _create_user(db, f"second_{uuid.uuid4().hex[:8]}@example.com")


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _upload(client: AsyncClient, token: str, name: str = "test.txt", content: bytes = b"hello",
                   folder_id: str | None = None) -> str:
    qs = f"?folder_id={folder_id}" if folder_id else ""
    resp = await client.post(f"/api/v1/files/upload{qs}",
        files={"file": (name, io.BytesIO(content), "text/plain")}, headers=_auth_headers(token))
    assert resp.status_code == 201
    return resp.json()["id"]


class TestPermissionAwareSearch:
    @pytest.mark.asyncio
    async def test_search_includes_shared_files(self, client: AsyncClient, db_session: AsyncSession):
        _, owner_token = await _create_user(db_session)
        collab_id, collab_token = await _create_second(db_session)
        fid = await _upload(client, owner_token, name="shared_doc.txt")
        await client.post(f"/api/v1/collaboration/share/file/{fid}",
                          json={"user_id": str(collab_id), "role": "viewer"},
                          headers=_auth_headers(owner_token))

        resp = await client.get("/api/v1/search?query=shared", headers=_auth_headers(collab_token))
        assert resp.status_code == 200
        assert resp.json()["total"] >= 1

    @pytest.mark.asyncio
    async def test_search_includes_inherited_files(self, client: AsyncClient, db_session: AsyncSession):
        _, owner_token = await _create_user(db_session)
        collab_id, collab_token = await _create_second(db_session)

        folder_resp = await client.post("/api/v1/folders", json={"name": "SharedFolder"},
                                        headers=_auth_headers(owner_token))
        folder_id = folder_resp.json()["id"]
        await _upload(client, owner_token, name="in_folder.txt", folder_id=folder_id)
        await client.post(
            f"/api/v1/collaboration/share/folder/{folder_id}",
            json={"user_id": str(collab_id), "role": "editor"},
            headers=_auth_headers(owner_token),
        )

        resp = await client.get("/api/v1/search?query=in_folder", headers=_auth_headers(collab_token))
        assert resp.status_code == 200
        assert resp.json()["total"] >= 1

    @pytest.mark.asyncio
    async def test_search_excludes_unauthorized_files(self, client: AsyncClient, db_session: AsyncSession):
        _, owner_token = await _create_user(db_session)
        _, other_token = await _create_second(db_session)
        await _upload(client, owner_token, name="private_doc.txt")

        resp = await client.get("/api/v1/search?query=private", headers=_auth_headers(other_token))
        assert resp.status_code == 200
        assert resp.json()["total"] == 0


class TestSuggestions:
    @pytest.mark.asyncio
    async def test_suggestions_return_matching_filenames(self, client: AsyncClient, db_session: AsyncSession):
        _, token = await _create_user(db_session)
        await _upload(client, token, name="report_2024.pdf")
        await _upload(client, token, name="report_2025.pdf")

        resp = await client.get("/api/v1/search/suggestions?query=report",
                                headers=_auth_headers(token))
        assert resp.status_code == 200
        assert len(resp.json()["suggestions"]) >= 1

    @pytest.mark.asyncio
    async def test_suggestions_require_auth(self, client: AsyncClient):
        resp = await client.get("/api/v1/search/suggestions?query=test")
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_suggestions_empty_for_no_match(self, client: AsyncClient, db_session: AsyncSession):
        _, token = await _create_user(db_session)

        resp = await client.get("/api/v1/search/suggestions?query=zzznotfound",
                                headers=_auth_headers(token))
        assert resp.status_code == 200
        assert resp.json()["suggestions"] == []


class TestRecentAutoRecord:
    @pytest.mark.asyncio
    async def test_upload_records_recent(self, client: AsyncClient, db_session: AsyncSession):
        _, token = await _create_user(db_session)
        await _upload(client, token)

        resp = await client.get("/api/v1/recent", headers=_auth_headers(token))
        assert resp.status_code == 200
        assert resp.json()["total"] >= 1

    @pytest.mark.asyncio
    async def test_download_records_recent(self, client: AsyncClient, db_session: AsyncSession):
        _, token = await _create_user(db_session)
        fid = await _upload(client, token)
        await client.get(f"/api/v1/files/{fid}/download", headers=_auth_headers(token))

        resp = await client.get("/api/v1/recent", headers=_auth_headers(token))
        assert resp.json()["total"] >= 1

    @pytest.mark.asyncio
    async def test_rename_records_recent(self, client: AsyncClient, db_session: AsyncSession):
        _, token = await _create_user(db_session)
        fid = await _upload(client, token, name="old.txt")
        await client.post(f"/api/v1/files/{fid}/rename", json={"name": "new.txt"},
                          headers=_auth_headers(token))

        resp = await client.get("/api/v1/recent", headers=_auth_headers(token))
        assert resp.json()["total"] >= 2
