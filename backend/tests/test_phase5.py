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


async def _create_second_user(db: AsyncSession) -> tuple[uuid.UUID, str]:
    return await _create_user(db, f"second_{uuid.uuid4().hex[:8]}@example.com")


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _upload(client: AsyncClient, token: str, name: str = "test.txt", folder_id: str | None = None) -> str:
    qs = f"?folder_id={folder_id}" if folder_id else ""
    resp = await client.post(f"/api/v1/files/upload{qs}",
        files={"file": (name, io.BytesIO(b"hello"), "text/plain")}, headers=_auth_headers(token))
    assert resp.status_code == 201
    return resp.json()["id"]


async def _create_folder(client: AsyncClient, token: str, name: str) -> str:
    resp = await client.post("/api/v1/folders", json={"name": name}, headers=_auth_headers(token))
    assert resp.status_code == 201
    return resp.json()["id"]


class TestShareResource:
    @pytest.mark.asyncio
    async def test_share_file_with_user(self, client: AsyncClient, db_session: AsyncSession):
        _, owner_token = await _create_user(db_session)
        collab_id, _ = await _create_second_user(db_session)
        fid = await _upload(client, owner_token)

        resp = await client.post(
            f"/api/v1/collaboration/share/file/{fid}",
            json={"user_id": str(collab_id), "role": "editor"},
            headers=_auth_headers(owner_token),
        )
        assert resp.status_code == 200
        assert resp.json()["role"] == "editor"
        assert resp.json()["user_id"] == str(collab_id)

    @pytest.mark.asyncio
    async def test_cannot_share_with_owner(self, client: AsyncClient, db_session: AsyncSession):
        owner_id, token = await _create_user(db_session)
        fid = await _upload(client, token)

        resp = await client.post(
            f"/api/v1/collaboration/share/file/{fid}",
            json={"user_id": str(owner_id), "role": "editor"},
            headers=_auth_headers(token),
        )
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_nonowner_cannot_share(self, client: AsyncClient, db_session: AsyncSession):
        _, owner_token = await _create_user(db_session)
        _, other_token = await _create_second_user(db_session)
        fid = await _upload(client, owner_token)

        resp = await client.post(
            f"/api/v1/collaboration/share/file/{fid}",
            json={"user_id": str(uuid.uuid4()), "role": "viewer"},
            headers=_auth_headers(other_token),
        )
        assert resp.status_code in (404, 422)

    @pytest.mark.asyncio
    async def test_get_resource_permissions(self, client: AsyncClient, db_session: AsyncSession):
        _, token = await _create_user(db_session)
        fid = await _upload(client, token)

        resp = await client.get(
            f"/api/v1/collaboration/permissions/file/{fid}",
            headers=_auth_headers(token),
        )
        assert resp.status_code == 200
        assert resp.json()["owner_id"] is not None


class TestSharedLinks:
    @pytest.mark.asyncio
    async def test_create_link(self, client: AsyncClient, db_session: AsyncSession):
        _, token = await _create_user(db_session)
        fid = await _upload(client, token)

        resp = await client.post(
            "/api/v1/collaboration/links",
            json={"resource_type": "file", "resource_id": fid, "is_public": True},
            headers=_auth_headers(token),
        )
        assert resp.status_code == 201
        assert "token" in resp.json()

    @pytest.mark.asyncio
    async def test_list_links(self, client: AsyncClient, db_session: AsyncSession):
        _, token = await _create_user(db_session)
        fid = await _upload(client, token)
        await client.post("/api/v1/collaboration/links",
            json={"resource_type": "file", "resource_id": fid}, headers=_auth_headers(token))

        resp = await client.get("/api/v1/collaboration/links", headers=_auth_headers(token))
        assert resp.status_code == 200
        assert len(resp.json()) >= 1

    @pytest.mark.asyncio
    async def test_delete_link(self, client: AsyncClient, db_session: AsyncSession):
        _, token = await _create_user(db_session)
        fid = await _upload(client, token)
        link_resp = await client.post("/api/v1/collaboration/links",
            json={"resource_type": "file", "resource_id": fid}, headers=_auth_headers(token))
        link_id = link_resp.json()["id"]

        resp = await client.delete(
            f"/api/v1/collaboration/links/{link_id}", headers=_auth_headers(token)
        )
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_create_password_protected_link(self, client: AsyncClient, db_session: AsyncSession):
        _, token = await _create_user(db_session)
        fid = await _upload(client, token)

        resp = await client.post(
            "/api/v1/collaboration/links",
            json={"resource_type": "file", "resource_id": fid, "password": "secret123"},
            headers=_auth_headers(token),
        )
        assert resp.status_code == 201
        assert "password_hash" not in resp.json()

    @pytest.mark.asyncio
    async def test_create_link_with_expiry(self, client: AsyncClient, db_session: AsyncSession):
        _, token = await _create_user(db_session)
        fid = await _upload(client, token)
        from datetime import UTC, datetime, timedelta
        future = (datetime.now(UTC) + timedelta(days=30)).isoformat()

        resp = await client.post(
            "/api/v1/collaboration/links",
            json={"resource_type": "file", "resource_id": fid, "expires_at": future},
            headers=_auth_headers(token),
        )
        assert resp.status_code == 201


class TestSharedWithMe:
    @pytest.mark.asyncio
    async def test_list_shared_with_me(self, client: AsyncClient, db_session: AsyncSession):
        _, owner_token = await _create_user(db_session)
        collab_id, collab_token = await _create_second_user(db_session)
        fid = await _upload(client, owner_token)
        await client.post(
            f"/api/v1/collaboration/share/file/{fid}",
            json={"user_id": str(collab_id), "role": "viewer"},
            headers=_auth_headers(owner_token),
        )

        resp = await client.get(
            "/api/v1/collaboration/shared-with-me", headers=_auth_headers(collab_token)
        )
        assert resp.status_code == 200
        assert resp.json()["total"] >= 1

    @pytest.mark.asyncio
    async def test_list_shared_by_me(self, client: AsyncClient, db_session: AsyncSession):
        _, owner_token = await _create_user(db_session)
        collab_id, _ = await _create_second_user(db_session)
        fid = await _upload(client, owner_token)
        await client.post(
            f"/api/v1/collaboration/share/file/{fid}",
            json={"user_id": str(collab_id), "role": "viewer"},
            headers=_auth_headers(owner_token),
        )

        resp = await client.get(
            "/api/v1/collaboration/shared-by-me", headers=_auth_headers(owner_token)
        )
        assert resp.status_code == 200
        assert resp.json()["total"] >= 1


class TestTransferOwnership:
    @pytest.mark.asyncio
    async def test_transfer_ownership(self, client: AsyncClient, db_session: AsyncSession):
        _, owner_token = await _create_user(db_session)
        new_owner_id, _ = await _create_second_user(db_session)
        fid = await _upload(client, owner_token)

        resp = await client.post(
            f"/api/v1/collaboration/transfer-ownership/file/{fid}",
            json={"new_owner_id": str(new_owner_id)},
            headers=_auth_headers(owner_token),
        )
        assert resp.status_code == 200

        detail = await client.get(f"/api/v1/files/{fid}", headers=_auth_headers(owner_token))
        assert detail.status_code == 404

    @pytest.mark.asyncio
    async def test_cannot_transfer_to_self(self, client: AsyncClient, db_session: AsyncSession):
        owner_id, token = await _create_user(db_session)
        fid = await _upload(client, token)

        resp = await client.post(
            f"/api/v1/collaboration/transfer-ownership/file/{fid}",
            json={"new_owner_id": str(owner_id)},
            headers=_auth_headers(token),
        )
        assert resp.status_code == 422


class TestPermissionInheritance:
    @pytest.mark.asyncio
    async def test_viewer_can_read_file(self, client: AsyncClient, db_session: AsyncSession):
        _, owner_token = await _create_user(db_session)
        collab_id, collab_token = await _create_second_user(db_session)
        fid = await _upload(client, owner_token)
        await client.post(
            f"/api/v1/collaboration/share/file/{fid}",
            json={"user_id": str(collab_id), "role": "viewer"},
            headers=_auth_headers(owner_token),
        )

        resp = await client.get(f"/api/v1/files/{fid}", headers=_auth_headers(collab_token))
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_inherited_folder_permission_applies_to_file(self, client: AsyncClient, db_session: AsyncSession):
        _, owner_token = await _create_user(db_session)
        collab_id, collab_token = await _create_second_user(db_session)
        folder_id = await _create_folder(client, owner_token, "SharedFolder")
        fid = await _upload(client, owner_token, folder_id=folder_id)
        await client.post(
            f"/api/v1/collaboration/share/folder/{folder_id}",
            json={"user_id": str(collab_id), "role": "viewer"},
            headers=_auth_headers(owner_token),
        )

        resp = await client.get(f"/api/v1/files/{fid}", headers=_auth_headers(collab_token))
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_commenter_cannot_write_file(self, client: AsyncClient, db_session: AsyncSession):
        _, owner_token = await _create_user(db_session)
        collab_id, collab_token = await _create_second_user(db_session)
        fid = await _upload(client, owner_token)
        await client.post(
            f"/api/v1/collaboration/share/file/{fid}",
            json={"user_id": str(collab_id), "role": "commenter"},
            headers=_auth_headers(owner_token),
        )

        resp = await client.delete(f"/api/v1/files/{fid}", headers=_auth_headers(collab_token))
        assert resp.status_code in (403, 404)


class TestPermissionAuthorization:
    @pytest.mark.asyncio
    async def test_effective_permission_for_owner_returns_owner(self, db_session: AsyncSession):
        from app.dependencies.permission import get_effective_permission
        from app.repositories.file import FileRepository

        owner_id = uuid.uuid4()
        file_repo = FileRepository(db_session)
        f = await file_repo.create(
            owner_id=owner_id, folder_id=None, original_filename="test.txt",
            stored_blob_name="blob", mime_type="text/plain", extension="txt",
            checksum_sha256="abc", file_size_bytes=10,
        )

        role = await get_effective_permission(db_session, owner_id, "file", f.id)
        assert role == "owner"

    @pytest.mark.asyncio
    async def test_effective_permission_returns_none_for_nonowner(self, db_session: AsyncSession):
        from app.dependencies.permission import get_effective_permission
        from app.repositories.file import FileRepository

        owner_id = uuid.uuid4()
        file_repo = FileRepository(db_session)
        f = await file_repo.create(
            owner_id=owner_id, folder_id=None, original_filename="test.txt",
            stored_blob_name="blob", mime_type="text/plain", extension="txt",
            checksum_sha256="abc", file_size_bytes=10,
        )

        role = await get_effective_permission(db_session, uuid.uuid4(), "file", f.id)
        assert role is None
