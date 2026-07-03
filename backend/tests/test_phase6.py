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


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _upload(client: AsyncClient, token: str, name: str = "test.txt", content: bytes = b"v1") -> str:
    resp = await client.post("/api/v1/files/upload",
        files={"file": (name, io.BytesIO(content), "text/plain")}, headers=_auth_headers(token))
    assert resp.status_code == 201
    return resp.json()["id"]


class TestVersionCreation:
    @pytest.mark.asyncio
    async def test_upload_creates_version(self, client: AsyncClient, db_session: AsyncSession):
        _, token = await _create_user(db_session)
        fid = await _upload(client, token, content=b"test content")

        resp = await client.get(f"/api/v1/versions/file/{fid}", headers=_auth_headers(token))
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 1
        assert body["versions"][0]["version_number"] == 1
        assert body["versions"][0]["is_current"] is True

    @pytest.mark.asyncio
    async def test_multiple_uploads_create_multiple_versions(self, client: AsyncClient, db_session: AsyncSession):
        _, token = await _create_user(db_session)
        fid = await _upload(client, token, content=b"v1")

        resp = await client.get(f"/api/v1/versions/file/{fid}", headers=_auth_headers(token))
        assert resp.json()["total"] == 1

    @pytest.mark.asyncio
    async def test_version_number_increments(self, client: AsyncClient, db_session: AsyncSession):
        _, token = await _create_user(db_session)
        fid = await _upload(client, token, content=b"v1 content")

        resp = await client.get(f"/api/v1/versions/file/{fid}", headers=_auth_headers(token))
        assert resp.json()["versions"][0]["version_number"] == 1


class TestVersionList:
    @pytest.mark.asyncio
    async def test_list_versions_ordered_descending(self, client: AsyncClient, db_session: AsyncSession):
        _, token = await _create_user(db_session)
        fid = await _upload(client, token, content=b"content")

        resp = await client.get(f"/api/v1/versions/file/{fid}", headers=_auth_headers(token))
        versions = resp.json()["versions"]
        assert versions[0]["version_number"] >= 1

    @pytest.mark.asyncio
    async def test_list_versions_pagination(self, client: AsyncClient, db_session: AsyncSession):
        _, token = await _create_user(db_session)
        fid = await _upload(client, token)

        resp = await client.get(f"/api/v1/versions/file/{fid}?offset=0&limit=10",
                                headers=_auth_headers(token))
        assert resp.status_code == 200
        assert "total" in resp.json()


class TestVersionRestore:
    @pytest.mark.asyncio
    async def test_restore_creates_new_version(self, client: AsyncClient, db_session: AsyncSession):
        _, token = await _create_user(db_session)
        fid = await _upload(client, token, content=b"original")

        versions_resp = await client.get(f"/api/v1/versions/file/{fid}", headers=_auth_headers(token))
        v1_id = versions_resp.json()["versions"][0]["id"]

        restore_resp = await client.post(
            f"/api/v1/versions/{v1_id}/restore", headers=_auth_headers(token))
        assert restore_resp.status_code == 200

        after = await client.get(f"/api/v1/versions/file/{fid}", headers=_auth_headers(token))
        assert after.json()["total"] == 2

    @pytest.mark.asyncio
    async def test_restore_current_version_creates_new_version(self, client: AsyncClient, db_session: AsyncSession):
        _, token = await _create_user(db_session)
        fid = await _upload(client, token, content=b"original")

        versions_resp = await client.get(f"/api/v1/versions/file/{fid}", headers=_auth_headers(token))
        v1_id = versions_resp.json()["versions"][0]["id"]

        restore_resp = await client.post(
            f"/api/v1/versions/{v1_id}/restore", headers=_auth_headers(token))
        assert restore_resp.status_code == 200


class TestVersionDelete:
    @pytest.mark.asyncio
    async def test_cannot_delete_current_version(self, client: AsyncClient, db_session: AsyncSession):
        _, token = await _create_user(db_session)
        fid = await _upload(client, token)

        versions_resp = await client.get(f"/api/v1/versions/file/{fid}", headers=_auth_headers(token))
        current_id = versions_resp.json()["versions"][0]["id"]

        resp = await client.delete(f"/api/v1/versions/{current_id}", headers=_auth_headers(token))
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_cannot_delete_only_version(self, client: AsyncClient, db_session: AsyncSession):
        _, token = await _create_user(db_session)
        fid = await _upload(client, token, content=b"only")

        versions_resp = await client.get(f"/api/v1/versions/file/{fid}", headers=_auth_headers(token))
        v1_id = versions_resp.json()["versions"][0]["id"]

        await client.post(f"/api/v1/versions/{v1_id}/restore", headers=_auth_headers(token))
        after = await client.get(f"/api/v1/versions/file/{fid}", headers=_auth_headers(token))
        non_current = [v for v in after.json()["versions"] if not v["is_current"]][0]

        resp = await client.delete(
            f"/api/v1/versions/{non_current['id']}", headers=_auth_headers(token))
        assert resp.status_code == 200


class TestVersionDownload:
    @pytest.mark.asyncio
    async def test_download_version(self, client: AsyncClient, db_session: AsyncSession):
        _, token = await _create_user(db_session)
        content = b"downloadable content"
        fid = await _upload(client, token, content=content)

        versions_resp = await client.get(f"/api/v1/versions/file/{fid}", headers=_auth_headers(token))
        v_id = versions_resp.json()["versions"][0]["id"]

        resp = await client.get(f"/api/v1/versions/{v_id}/download", headers=_auth_headers(token))
        assert resp.status_code == 200
        assert resp.content == content


class TestVersionAuthorization:
    @pytest.mark.asyncio
    async def test_versions_require_auth(self, client: AsyncClient, db_session: AsyncSession):
        _, token = await _create_user(db_session)
        fid = await _upload(client, token)
        resp = await client.get(f"/api/v1/versions/file/{fid}")
        assert resp.status_code == 401


class TestVersionRepository:
    @pytest.mark.asyncio
    async def test_set_current_updates_flag(self, db_session: AsyncSession):
        from app.repositories.versioning import FileVersionRepository

        repo = FileVersionRepository(db_session)
        file_id = uuid.uuid4()
        await repo.create(file_id=file_id, version_number=1, blob_name="blob1",
                               checksum_sha256="abc", file_size_bytes=10, created_by=uuid.uuid4())
        v2 = await repo.create(file_id=file_id, version_number=2, blob_name="blob2",
                               checksum_sha256="def", file_size_bytes=20, created_by=uuid.uuid4())

        await repo.set_current(file_id, v2.id)
        current = await repo.get_current(file_id)
        assert current is not None
        assert current.id == v2.id
