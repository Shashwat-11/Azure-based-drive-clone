from __future__ import annotations

import io
import uuid
from collections.abc import AsyncIterator

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.jwt import create_access_token
from app.auth.password import hash_password
from app.models.user import UserRole
from app.repositories.user import UserRepository


async def _create_user(db: AsyncSession, email: str = "test@example.com") -> tuple[uuid.UUID, str]:
    repo = UserRepository(db)
    user = await repo.create(
        email=email,
        password_hash=hash_password("securePassword123"),
        full_name="Test User",
    )
    token = create_access_token(user.id, UserRole.USER.value)
    return user.id, token


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


class TestFolderAPI:
    @pytest.mark.asyncio
    async def test_create_folder(self, client: AsyncClient, db_session: AsyncSession):
        user_id, token = await _create_user(db_session)

        response = await client.post(
            "/api/v1/folders",
            json={"name": "Documents"},
            headers=_auth_headers(token),
        )
        assert response.status_code == 201
        body = response.json()
        assert body["name"] == "Documents"
        assert body["owner_id"] == str(user_id)
        assert body["parent_id"] is None

    @pytest.mark.asyncio
    async def test_create_nested_folder(self, client: AsyncClient, db_session: AsyncSession):
        user_id, token = await _create_user(db_session)

        parent_resp = await client.post(
            "/api/v1/folders",
            json={"name": "Parent"},
            headers=_auth_headers(token),
        )
        parent_id = parent_resp.json()["id"]

        child_resp = await client.post(
            "/api/v1/folders",
            json={"name": "Child", "parent_id": parent_id},
            headers=_auth_headers(token),
        )
        assert child_resp.status_code == 201
        assert child_resp.json()["parent_id"] == parent_id

    @pytest.mark.asyncio
    async def test_create_duplicate_folder_fails(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        user_id, token = await _create_user(db_session)

        await client.post(
            "/api/v1/folders",
            json={"name": "Docs"},
            headers=_auth_headers(token),
        )
        response = await client.post(
            "/api/v1/folders",
            json={"name": "Docs"},
            headers=_auth_headers(token),
        )
        assert response.status_code == 409

    @pytest.mark.asyncio
    async def test_create_folder_requires_auth(self, client: AsyncClient):
        response = await client.post("/api/v1/folders", json={"name": "Test"})
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_list_folders(self, client: AsyncClient, db_session: AsyncSession):
        user_id, token = await _create_user(db_session)

        await client.post(
            "/api/v1/folders", json={"name": "Alpha"}, headers=_auth_headers(token)
        )
        await client.post(
            "/api/v1/folders", json={"name": "Beta"}, headers=_auth_headers(token)
        )

        response = await client.get("/api/v1/folders", headers=_auth_headers(token))
        assert response.status_code == 200
        body = response.json()
        assert body["total"] == 2
        assert len(body["folders"]) == 2

    @pytest.mark.asyncio
    async def test_list_folders_by_parent(self, client: AsyncClient, db_session: AsyncSession):
        user_id, token = await _create_user(db_session)

        parent_resp = await client.post(
            "/api/v1/folders", json={"name": "Parent"}, headers=_auth_headers(token)
        )
        parent_id = parent_resp.json()["id"]

        await client.post(
            "/api/v1/folders",
            json={"name": "Child", "parent_id": parent_id},
            headers=_auth_headers(token),
        )

        response = await client.get(
            f"/api/v1/folders?parent_id={parent_id}", headers=_auth_headers(token)
        )
        assert response.status_code == 200
        assert response.json()["total"] == 1

    @pytest.mark.asyncio
    async def test_get_folder(self, client: AsyncClient, db_session: AsyncSession):
        user_id, token = await _create_user(db_session)

        create_resp = await client.post(
            "/api/v1/folders", json={"name": "Docs"}, headers=_auth_headers(token)
        )
        folder_id = create_resp.json()["id"]

        response = await client.get(
            f"/api/v1/folders/{folder_id}", headers=_auth_headers(token)
        )
        assert response.status_code == 200
        assert response.json()["id"] == folder_id

    @pytest.mark.asyncio
    async def test_get_nonexistent_folder_returns_404(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        _, token = await _create_user(db_session)
        response = await client.get(
            f"/api/v1/folders/{uuid.uuid4()}", headers=_auth_headers(token)
        )
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_update_folder_name(self, client: AsyncClient, db_session: AsyncSession):
        _, token = await _create_user(db_session)

        create_resp = await client.post(
            "/api/v1/folders", json={"name": "Old Name"}, headers=_auth_headers(token)
        )
        folder_id = create_resp.json()["id"]

        response = await client.patch(
            f"/api/v1/folders/{folder_id}",
            json={"name": "New Name"},
            headers=_auth_headers(token),
        )
        assert response.status_code == 200
        assert response.json()["name"] == "New Name"

    @pytest.mark.asyncio
    async def test_delete_folder(self, client: AsyncClient, db_session: AsyncSession):
        _, token = await _create_user(db_session)

        create_resp = await client.post(
            "/api/v1/folders", json={"name": "ToDelete"}, headers=_auth_headers(token)
        )
        folder_id = create_resp.json()["id"]

        response = await client.delete(
            f"/api/v1/folders/{folder_id}", headers=_auth_headers(token)
        )
        assert response.status_code == 200
        assert response.json()["success"] is True

        get_resp = await client.get(
            f"/api/v1/folders/{folder_id}", headers=_auth_headers(token)
        )
        assert get_resp.status_code == 404


class MockStorageBackend:
    def __init__(self):
        self.blobs: dict[str, bytes] = {}
        self.deleted: list[str] = []
        self.upload_call_count = 0

    async def upload(self, blob_name: str, data: bytes, *, content_type=None, metadata=None) -> str:
        self.blobs[blob_name] = data
        return blob_name

    async def upload_stream(
        self,
        blob_name: str,
        stream: AsyncIterator[bytes],
        *,
        content_type=None,
        metadata=None,
    ) -> str:
        chunks: list[bytes] = []
        async for chunk in stream:
            chunks.append(chunk)
        self.blobs[blob_name] = b"".join(chunks)
        self.upload_call_count += 1
        return blob_name

    async def download(self, blob_name: str) -> bytes:
        return self.blobs.get(blob_name, b"")

    async def download_stream(self, blob_name: str) -> AsyncIterator[bytes]:
        data = self.blobs.get(blob_name, b"")
        chunk_size = 64 * 1024
        for i in range(0, len(data), chunk_size):
            yield data[i : i + chunk_size]

    async def delete(self, blob_name: str) -> None:
        self.deleted.append(blob_name)
        self.blobs.pop(blob_name, None)

    async def delete_batch(self, blob_names: list[str]) -> None:
        for name in blob_names:
            await self.delete(name)

    async def exists(self, blob_name: str) -> bool:
        return blob_name in self.blobs

    async def copy(self, source_blob: str, destination_blob: str) -> str:
        if source_blob in self.blobs:
            self.blobs[destination_blob] = self.blobs[source_blob]
        return destination_blob

    async def move(self, source_blob: str, destination_blob: str) -> str:
        await self.copy(source_blob, destination_blob)
        await self.delete(source_blob)
        return destination_blob

    async def health_check(self) -> bool:
        return True

    async def close(self) -> None:
        pass


class TestFileUpload:
    @pytest.mark.asyncio
    async def test_upload_file_stores_metadata(self, client: AsyncClient, db_session: AsyncSession):
        user_id, token = await _create_user(db_session)

        file_content = b"Hello, world! This is test content."
        files_data = {"file": ("test.txt", io.BytesIO(file_content), "text/plain")}

        response = await client.post(
            "/api/v1/files/upload",
            files=files_data,
            headers=_auth_headers(token),
        )
        assert response.status_code == 201
        body = response.json()
        assert body["original_filename"] == "test.txt"
        assert body["mime_type"] == "text/plain"
        assert body["extension"] == "txt"
        assert body["file_size_bytes"] > 0
        assert body["checksum_sha256"] is not None
        assert body["owner_id"] == str(user_id)
        assert "stored_blob_name" not in body
        assert "storage_provider" not in body

    @pytest.mark.asyncio
    async def test_upload_file_in_folder(self, client: AsyncClient, db_session: AsyncSession):
        _, token = await _create_user(db_session)

        folder_resp = await client.post(
            "/api/v1/folders", json={"name": "Uploads"}, headers=_auth_headers(token)
        )
        folder_id = folder_resp.json()["id"]

        files_data = {"file": ("doc.txt", io.BytesIO(b"content"), "text/plain")}
        response = await client.post(
            f"/api/v1/files/upload?folder_id={folder_id}",
            files=files_data,
            headers=_auth_headers(token),
        )
        assert response.status_code == 201
        assert response.json()["folder_id"] == folder_id

    @pytest.mark.asyncio
    async def test_upload_requires_auth(self, client: AsyncClient):
        files_data = {"file": ("test.txt", io.BytesIO(b"test"), "text/plain")}
        response = await client.post("/api/v1/files/upload", files=files_data)
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_upload_with_special_chars_in_filename(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        _, token = await _create_user(db_session)

        files_data = {"file": ("my file (v2).txt", io.BytesIO(b"content"), "text/plain")}
        response = await client.post(
            "/api/v1/files/upload",
            files=files_data,
            headers=_auth_headers(token),
        )
        assert response.status_code == 201

    @pytest.mark.asyncio
    async def test_checksum_correctness(self, client: AsyncClient, db_session: AsyncSession):
        import hashlib
        _, token = await _create_user(db_session)

        content = b"Verify checksum integrity" * 100
        expected_hash = hashlib.sha256(content).hexdigest()

        files_data = {
            "file": ("checksum-test.bin", io.BytesIO(content), "application/octet-stream")
        }
        response = await client.post(
            "/api/v1/files/upload",
            files=files_data,
            headers=_auth_headers(token),
        )
        assert response.status_code == 201
        assert response.json()["checksum_sha256"] == expected_hash


class TestFileOperations:
    @pytest.mark.asyncio
    async def test_list_files(self, client: AsyncClient, db_session: AsyncSession):
        _, token = await _create_user(db_session)

        await client.post(
            "/api/v1/files/upload",
            files={"file": ("a.txt", io.BytesIO(b"a"), "text/plain")},
            headers=_auth_headers(token),
        )
        await client.post(
            "/api/v1/files/upload",
            files={"file": ("b.txt", io.BytesIO(b"b"), "text/plain")},
            headers=_auth_headers(token),
        )

        response = await client.get("/api/v1/files", headers=_auth_headers(token))
        assert response.status_code == 200
        body = response.json()
        assert body["total"] == 2

    @pytest.mark.asyncio
    async def test_get_file_metadata(self, client: AsyncClient, db_session: AsyncSession):
        _, token = await _create_user(db_session)

        upload_resp = await client.post(
            "/api/v1/files/upload",
            files={"file": ("info.txt", io.BytesIO(b"data"), "text/plain")},
            headers=_auth_headers(token),
        )
        file_id = upload_resp.json()["id"]

        response = await client.get(f"/api/v1/files/{file_id}", headers=_auth_headers(token))
        assert response.status_code == 200
        assert response.json()["id"] == file_id

    @pytest.mark.asyncio
    async def test_delete_file(self, client: AsyncClient, db_session: AsyncSession):
        _, token = await _create_user(db_session)

        upload_resp = await client.post(
            "/api/v1/files/upload",
            files={"file": ("delete-me.txt", io.BytesIO(b"bye"), "text/plain")},
            headers=_auth_headers(token),
        )
        file_id = upload_resp.json()["id"]

        response = await client.delete(f"/api/v1/files/{file_id}", headers=_auth_headers(token))
        assert response.status_code == 200
        assert response.json()["success"] is True

        get_resp = await client.get(f"/api/v1/files/{file_id}", headers=_auth_headers(token))
        assert get_resp.status_code == 404

    @pytest.mark.asyncio
    async def test_download_file_streaming(self, client: AsyncClient, db_session: AsyncSession):
        _, token = await _create_user(db_session)

        content = b"Streaming download test content" * 50
        files_data = {"file": ("stream.txt", io.BytesIO(content), "text/plain")}

        upload_resp = await client.post(
            "/api/v1/files/upload",
            files=files_data,
            headers=_auth_headers(token),
        )
        file_id = upload_resp.json()["id"]
        expected_size = upload_resp.json()["file_size_bytes"]

        response = await client.get(
            f"/api/v1/files/{file_id}/download",
            headers=_auth_headers(token),
        )
        assert response.status_code == 200
        assert "text/plain" in response.headers.get("content-type", "")
        assert "Content-Disposition" in response.headers
        assert response.headers.get("Content-Length") == str(expected_size)
        assert response.content == content


class TestTransactionRollback:
    @pytest.mark.asyncio
    async def test_upload_compensation_deletes_blob_on_db_failure(self, db_session: AsyncSession):
        from io import BytesIO
        from unittest.mock import AsyncMock

        from starlette.datastructures import Headers

        from app.services.file import FileService
        from app.services.storage import StorageService

        mock_storage = MockStorageBackend()
        storage_service = StorageService(backend=mock_storage)
        file_service = FileService(db_session, storage_service=storage_service)

        file_service.repo.create = AsyncMock(
            side_effect=Exception("DB insert failure")
        )

        content = b"test data"
        test_file = type("FakeUploadFile", (), {})()
        test_file.filename = "test.txt"
        test_file.file = BytesIO(content)
        test_file.size = len(content)
        test_file.content_type = "text/plain"
        test_file.headers = Headers({"content-type": "text/plain"})

        async def mock_read(size):
            return test_file.file.read(size)

        test_file.read = mock_read

        with pytest.raises(Exception, match="Failed to save file metadata"):
            user_id = uuid.uuid4()
            await file_service.upload(test_file, user_id)

        assert len(mock_storage.deleted) >= 1

    @pytest.mark.asyncio
    async def test_delete_does_not_rollback_on_blob_failure(self, db_session: AsyncSession):
        from app.services.file import FileService
        from app.services.storage import StorageService

        mock_storage = MockStorageBackend()
        storage_service = StorageService(backend=mock_storage)

        blob_name = storage_service.generate_blob_name(uuid.uuid4())
        mock_storage.blobs[blob_name] = b"test"

        from app.repositories.file import FileRepository
        repo = FileRepository(db_session)
        user_id = uuid.uuid4()

        file_record = await repo.create(
            owner_id=user_id,
            folder_id=None,
            original_filename="test.txt",
            stored_blob_name=blob_name,
            mime_type="text/plain",
            extension="txt",
            checksum_sha256="abc123",
            file_size_bytes=100,
        )

        mock_storage.blobs.pop(blob_name)

        file_service = FileService(db_session, storage_service=storage_service)
        await file_service.delete(file_record.id, user_id)

        deleted_record = await repo.get_by_id(file_record.id, user_id)
        assert deleted_record is None


class TestValidation:
    @pytest.mark.asyncio
    async def test_reject_filename_with_slash(self, client: AsyncClient, db_session: AsyncSession):
        _, token = await _create_user(db_session)
        files_data = {"file": ("path/traversal.txt", io.BytesIO(b"bad"), "text/plain")}
        response = await client.post(
            "/api/v1/files/upload",
            files=files_data,
            headers=_auth_headers(token),
        )
        assert response.status_code in (400, 422)

    @pytest.mark.asyncio
    async def test_reject_empty_folder_name(self, client: AsyncClient, db_session: AsyncSession):
        _, token = await _create_user(db_session)
        response = await client.post(
            "/api/v1/folders",
            json={"name": ""},
            headers=_auth_headers(token),
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_create_folder_nonexistent_parent(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        _, token = await _create_user(db_session)
        response = await client.post(
            "/api/v1/folders",
            json={"name": "Orphan", "parent_id": str(uuid.uuid4())},
            headers=_auth_headers(token),
        )
        assert response.status_code == 404


class TestStorageService:
    @pytest.mark.asyncio
    async def test_generate_blob_name_contains_user_id(self):
        from app.services.storage import StorageService

        service = StorageService(backend=MockStorageBackend())
        user_id = uuid.uuid4()
        blob_name = service.generate_blob_name(user_id)
        assert str(user_id) in blob_name

    @pytest.mark.asyncio
    async def test_generate_blob_names_are_unique(self):
        from app.services.storage import StorageService

        service = StorageService(backend=MockStorageBackend())
        user_id = uuid.uuid4()
        names = {service.generate_blob_name(user_id) for _ in range(100)}
        assert len(names) == 100

    @pytest.mark.asyncio
    async def test_upload_and_hash_computes_correct_checksum(self):
        import hashlib

        from app.services.storage import StorageService

        service = StorageService(backend=MockStorageBackend())
        blob_name = str(uuid.uuid4())
        content = b"hash verification data" * 20
        expected_hash = hashlib.sha256(content).hexdigest()

        async def test_stream() -> AsyncIterator[bytes]:
            yield content

        size, checksum = await service.upload_and_hash(blob_name, test_stream())
        assert checksum == expected_hash
        assert size == len(content)


class TestFileServiceValidation:
    @pytest.mark.asyncio
    async def test_validate_extension_allowed(self, db_session: AsyncSession):
        from app.services.file import FileService

        service = FileService(db_session)
        assert service._validate_extension("document.pdf") == "pdf"

    @pytest.mark.asyncio
    async def test_validate_extension_no_extension(self, db_session: AsyncSession):
        from app.services.file import FileService

        service = FileService(db_session)
        assert service._validate_extension("noextension") is None

    @pytest.mark.asyncio
    async def test_validate_mime_type_rejects_null_byte(self, db_session: AsyncSession):
        from app.core.exceptions import ValidationError
        from app.services.file import FileService

        service = FileService(db_session)
        with pytest.raises(ValidationError):
            service._validate_mime_type("text/plain\x00malicious")


class TestRepositoryQueries:
    @pytest.mark.asyncio
    async def test_list_folders_pagination(self, db_session: AsyncSession):
        from app.repositories.file import FolderRepository

        user_id = uuid.uuid4()
        repo = FolderRepository(db_session)

        for i in range(5):
            await repo.create(f"Folder_{i}", owner_id=user_id)

        folders, total = await repo.list_folders(user_id, offset=0, limit=3)
        assert len(folders) == 3
        assert total == 5

    @pytest.mark.asyncio
    async def test_list_files_by_folder(self, db_session: AsyncSession):
        from app.repositories.file import FileRepository, FolderRepository

        user_id = uuid.uuid4()
        folder_repo = FolderRepository(db_session)
        folder = await folder_repo.create("Files", owner_id=user_id)

        file_repo = FileRepository(db_session)
        await file_repo.create(
            owner_id=user_id,
            folder_id=folder.id,
            original_filename="in_folder.txt",
            stored_blob_name="blob1",
            mime_type="text/plain",
            extension="txt",
            checksum_sha256="abc",
            file_size_bytes=10,
        )
        await file_repo.create(
            owner_id=user_id,
            folder_id=None,
            original_filename="root_file.txt",
            stored_blob_name="blob2",
            mime_type="text/plain",
            extension="txt",
            checksum_sha256="def",
            file_size_bytes=20,
        )

        in_folder, total_in = await file_repo.list_files(user_id, folder_id=folder.id)
        assert len(in_folder) == 1

        root, total_root = await file_repo.list_files(user_id, folder_id=None)
        assert len(root) == 1

    @pytest.mark.asyncio
    async def test_folder_deleted_files_not_listed(self, db_session: AsyncSession):
        from app.repositories.file import FolderRepository

        user_id = uuid.uuid4()
        repo = FolderRepository(db_session)
        folder = await repo.create("Temp", owner_id=user_id)
        await repo.soft_delete(folder)

        folders, total = await repo.list_folders(user_id)
        assert len(folders) == 0
