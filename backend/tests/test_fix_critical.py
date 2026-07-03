from __future__ import annotations

import io
import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.jwt import create_access_token
from app.auth.password import hash_password
from app.models.user import UserRole
from app.repositories.file import FolderRepository
from app.repositories.user import UserRepository


async def _create_user(db: AsyncSession, email: str = "test@example.com") -> tuple[uuid.UUID, str]:
    repo = UserRepository(db)
    user = await repo.create(email=email, password_hash=hash_password("securePassword123"), full_name="Test User")
    token = create_access_token(user.id, UserRole.USER.value)
    return user.id, token


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _upload_file(client: AsyncClient, token: str, name: str = "test.txt", content: bytes = b"hello",
                        folder_id: str | None = None) -> str:
    qs = f"?folder_id={folder_id}" if folder_id else ""
    resp = await client.post(f"/api/v1/files/upload{qs}", files={"file": (name, io.BytesIO(content), "text/plain")},
                             headers=_auth_headers(token))
    assert resp.status_code == 201
    return resp.json()["id"]


async def _create_folder(client: AsyncClient, token: str, name: str, parent_id: str | None = None) -> str:
    body = {"name": name}
    if parent_id:
        body["parent_id"] = parent_id
    resp = await client.post("/api/v1/folders", json=body, headers=_auth_headers(token))
    assert resp.status_code == 201
    return resp.json()["id"]


class TestEmptyTrashBatching:
    """CRI-004: Verify empty_trash processes all items across batches."""

    @pytest.mark.asyncio
    async def test_empty_trash_clears_all_items(self, client: AsyncClient, db_session: AsyncSession):
        _, token = await _create_user(db_session)

        for i in range(5):
            fid = await _upload_file(client, token, name=f"file_{i}.txt")
            await client.delete(f"/api/v1/files/{fid}", headers=_auth_headers(token))

        resp = await client.post("/api/v1/folders/trash/empty", headers=_auth_headers(token))
        assert resp.status_code == 200

        trash = await client.get("/api/v1/folders/trash/all", headers=_auth_headers(token))
        assert trash.json()["total"] == 0

    @pytest.mark.asyncio
    async def test_empty_trash_handles_already_empty(self, client: AsyncClient, db_session: AsyncSession):
        _, token = await _create_user(db_session)

        resp = await client.post("/api/v1/folders/trash/empty", headers=_auth_headers(token))
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_empty_trash_clears_nested_folders(self, client: AsyncClient, db_session: AsyncSession):
        _, token = await _create_user(db_session)

        parent = await _create_folder(client, token, "P")
        child = await _create_folder(client, token, "C", parent_id=parent)
        await _upload_file(client, token, folder_id=child)
        await client.delete(f"/api/v1/folders/{parent}", headers=_auth_headers(token))

        resp = await client.post("/api/v1/folders/trash/empty", headers=_auth_headers(token))
        assert resp.status_code == 200

        trash = await client.get("/api/v1/folders/trash/all", headers=_auth_headers(token))
        assert trash.json()["total"] == 0

    @pytest.mark.asyncio
    async def test_empty_trash_batch_processing_loop(self, db_session: AsyncSession):
        """Direct service test: verify loop continues until trash is empty."""
        from app.services.folder import FolderService

        owner_id = uuid.uuid4()

        repo = FolderRepository(db_session)
        folder = await repo.create("BatchFolder", owner_id=owner_id)
        folder.soft_delete()
        await repo.update(folder)

        service = FolderService(db_session)
        count = await service.empty_trash(owner_id)

        assert count >= 1

        folders, _ = await repo.list_trash(owner_id)
        assert len(folders) == 0


class TestEmptyTrashBlobCleanup:
    """CRI-005: Verify empty_trash cleans up Azure blobs."""

    @pytest.mark.asyncio
    async def test_blob_cleanup_invoked_on_empty_trash(self, db_session: AsyncSession):
        from unittest.mock import AsyncMock

        from app.services.folder import FolderService
        from app.services.storage import StorageService

        mock_backend = type("FakeBackend", (), {})()
        mock_backend.blobs = {}
        mock_backend.deleted = []
        mock_backend.upload_stream = AsyncMock()
        mock_backend.delete = AsyncMock(side_effect=lambda name: mock_backend.deleted.append(name))
        mock_backend.delete_batch = AsyncMock(
            side_effect=lambda names: mock_backend.deleted.extend(names)
        )
        mock_backend.download = AsyncMock()
        mock_backend.download_stream = AsyncMock()
        mock_backend.exists = AsyncMock()
        mock_backend.copy = AsyncMock()
        mock_backend.move = AsyncMock()
        mock_backend.health_check = AsyncMock(return_value=True)
        mock_backend.close = AsyncMock()

        storage = StorageService(backend=mock_backend)
        owner_id = uuid.uuid4()

        repo = FolderRepository(db_session)
        from app.repositories.file import FileRepository
        file_repo = FileRepository(db_session)

        folder = await repo.create("CleanupFolder", owner_id=owner_id)
        blob_name = f"{owner_id}/test-blob-{uuid.uuid4().hex[:8]}"
        await file_repo.create(
            owner_id=owner_id, folder_id=folder.id, original_filename="test.txt",
            stored_blob_name=blob_name, mime_type="text/plain", extension="txt",
            checksum_sha256="abc", file_size_bytes=100,
        )

        folder.soft_delete()
        await repo.update(folder)

        service = FolderService(db_session, storage_service=storage)
        await service.empty_trash(owner_id)

        assert blob_name in mock_backend.deleted

    @pytest.mark.asyncio
    async def test_blob_cleanup_failure_logged_not_raised(self, db_session: AsyncSession):
        from unittest.mock import AsyncMock

        from app.services.folder import FolderService
        from app.services.storage import StorageService

        mock_backend = type("FakeBackend", (), {})()
        mock_backend.deleted = []
        mock_backend.upload_stream = AsyncMock()

        async def failing_delete(name):
            mock_backend.deleted.append(name)
            raise Exception("Azure transient error")

        mock_backend.delete = failing_delete
        mock_backend.delete_batch = AsyncMock()
        mock_backend.download = AsyncMock()
        mock_backend.download_stream = AsyncMock()
        mock_backend.exists = AsyncMock()
        mock_backend.copy = AsyncMock()
        mock_backend.move = AsyncMock()
        mock_backend.health_check = AsyncMock(return_value=True)
        mock_backend.close = AsyncMock()

        storage = StorageService(backend=mock_backend)
        owner_id = uuid.uuid4()

        from app.repositories.file import FileRepository

        file_repo = FileRepository(db_session)
        blob_name = f"{owner_id}/fail-blob-{uuid.uuid4().hex[:8]}"
        file_record = await file_repo.create(
            owner_id=owner_id, folder_id=None, original_filename="orphan.txt",
            stored_blob_name=blob_name, mime_type="text/plain", extension="txt",
            checksum_sha256="abc", file_size_bytes=100,
        )

        file_record.soft_delete()
        db_session.add(file_record)
        await db_session.flush()

        service = FolderService(db_session, storage_service=storage)
        count = await service.empty_trash(owner_id)

        assert count >= 0


class TestBreadcrumbAuthorization:
    """HIG-011: Verify breadcrumbs enforce owner scoping."""

    @pytest.mark.asyncio
    async def test_breadcrumbs_returns_path_for_owner(self, client: AsyncClient, db_session: AsyncSession):
        _, token = await _create_user(db_session)
        root = await _create_folder(client, token, "Home")
        child = await _create_folder(client, token, "Docs", parent_id=root)

        resp = await client.get(f"/api/v1/folders/{child}/breadcrumbs", headers=_auth_headers(token))
        assert resp.status_code == 200
        crumbs = resp.json()["breadcrumbs"]
        names = [c["name"] for c in crumbs]
        assert "Home" in names
        assert "Docs" in names

    @pytest.mark.asyncio
    async def test_breadcrumbs_rejects_cross_user_access(self, client: AsyncClient, db_session: AsyncSession):
        user1_id, token1 = await _create_user(db_session, email="alice@example.com")
        _, token2 = await _create_user(db_session, email="bob@example.com")

        alice_folder = await _create_folder(client, token1, "AliceSecret")

        resp = await client.get(
            f"/api/v1/folders/{alice_folder}/breadcrumbs",
            headers=_auth_headers(token2),
        )
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_breadcrumbs_owner_scoped_parent_check(self, db_session: AsyncSession):
        """Direct repo test: parent walk stops when owner changes."""
        repo = FolderRepository(db_session)

        alice = uuid.uuid4()
        bob = uuid.uuid4()

        alice_root = await repo.create("AliceRoot", owner_id=alice)
        alice_child = await repo.create("AliceChild", owner_id=alice, parent_id=alice_root.id)

        crumbs = await repo.get_breadcrumbs(alice_child.id, bob)
        assert len(crumbs) == 0

        crumbs_alice = await repo.get_breadcrumbs(alice_child.id, alice)
        assert len(crumbs_alice) >= 2

    @pytest.mark.asyncio
    async def test_breadcrumbs_nonexistent_folder_returns_404(self, client: AsyncClient, db_session: AsyncSession):
        _, token = await _create_user(db_session)
        resp = await client.get(
            f"/api/v1/folders/{uuid.uuid4()}/breadcrumbs",
            headers=_auth_headers(token),
        )
        assert resp.status_code == 404
