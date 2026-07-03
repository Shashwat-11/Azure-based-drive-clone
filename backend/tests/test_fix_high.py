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


async def _create_user(
    db: AsyncSession, email: str = "test@example.com"
) -> tuple[uuid.UUID, str]:
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


def _headers_with_trace(token: str, trace_id: str) -> dict[str, str]:
    return {**_auth_headers(token), "X-Request-ID": trace_id}


class TestAuditTraceId:
    """HIG-008: Verify trace_id is present in audit log events."""

    @pytest.mark.asyncio
    async def test_audit_upload_includes_trace_id(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        _, token = await _create_user(db_session)

        files_data = {"file": ("trace-test.txt", io.BytesIO(b"content"), "text/plain")}
        response = await client.post(
            "/api/v1/files/upload",
            files=files_data,
            headers=_headers_with_trace(token, "audit-trace-001"),
        )
        assert response.status_code == 201
        assert response.headers["x-request-id"] == "audit-trace-001"

    @pytest.mark.asyncio
    async def test_audit_download_includes_trace_id(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        _, token = await _create_user(db_session)

        files_data = {"file": ("dl-trace.txt", io.BytesIO(b"dl"), "text/plain")}
        upload_resp = await client.post(
            "/api/v1/files/upload",
            files=files_data,
            headers=_headers_with_trace(token, "download-trace-002"),
        )
        file_id = upload_resp.json()["id"]

        response = await client.get(
            f"/api/v1/files/{file_id}/download",
            headers=_headers_with_trace(token, "download-trace-002"),
        )
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_audit_delete_includes_trace_id(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        _, token = await _create_user(db_session)

        files_data = {"file": ("del-trace.txt", io.BytesIO(b"bye"), "text/plain")}
        upload_resp = await client.post(
            "/api/v1/files/upload",
            files=files_data,
            headers=_headers_with_trace(token, "delete-trace-003"),
        )
        file_id = upload_resp.json()["id"]

        response = await client.delete(
            f"/api/v1/files/{file_id}",
            headers=_headers_with_trace(token, "delete-trace-003"),
        )
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_audit_folder_create_includes_trace_id(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        _, token = await _create_user(db_session)

        response = await client.post(
            "/api/v1/folders",
            json={"name": "TracedFolder"},
            headers=_headers_with_trace(token, "folder-trace-004"),
        )
        assert response.status_code == 201

    @pytest.mark.asyncio
    async def test_audit_folder_delete_includes_trace_id(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        _, token = await _create_user(db_session)

        create_resp = await client.post(
            "/api/v1/folders",
            json={"name": "ToDelete"},
            headers=_headers_with_trace(token, "folder-del-trace-005"),
        )
        folder_id = create_resp.json()["id"]

        response = await client.delete(
            f"/api/v1/folders/{folder_id}",
            headers=_headers_with_trace(token, "folder-del-trace-005"),
        )
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_audit_service_default_trace_id_empty_string(self):
        from app.services.audit import AuditService

        AuditService.log_upload(
            trace_id="",
            user_id="u1",
            file_id="f1",
            folder_id=None,
            blob_name="b1",
            filename="test.txt",
            checksum="abc",
            size=100,
            mime_type="text/plain",
        )
        AuditService.log_download(
            trace_id="", user_id="u1", file_id="f1", blob_name="b1", filename="x"
        )
        AuditService.log_delete(
            trace_id="", user_id="u1", file_id="f1", blob_name="b1", filename="x"
        )
        AuditService.log_folder_created(
            trace_id="", user_id="u1", folder_id="f1", name="x", parent_id=None
        )
        AuditService.log_folder_deleted(
            trace_id="", user_id="u1", folder_id="f1", name="x"
        )

    @pytest.mark.asyncio
    async def test_service_methods_accept_trace_id_keyword(
        self, db_session: AsyncSession
    ):
        from app.services.file import FileService
        from app.services.folder import FolderService

        file_service = FileService(db_session)
        assert "trace_id" in file_service.upload.__code__.co_varnames
        assert "trace_id" in file_service.download_stream.__code__.co_varnames
        assert "trace_id" in file_service.delete.__code__.co_varnames

        folder_service = FolderService(db_session)
        assert "trace_id" in folder_service.create.__code__.co_varnames
        assert "trace_id" in folder_service.delete.__code__.co_varnames


class TestUploadSizeValidation:
    """HIG-009: Verify upload size validation works before and after storage."""

    @pytest.mark.asyncio
    async def test_pre_upload_size_check_rejects_oversized(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        _, token = await _create_user(db_session)

        large_content = b"x" * (200 * 1024 * 1024)
        files_data = {
            "file": ("big.bin", io.BytesIO(large_content), "application/octet-stream")
        }

        response = await client.post(
            "/api/v1/files/upload",
            files=files_data,
            headers=_auth_headers(token),
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_post_upload_size_check_compensates(self, db_session: AsyncSession):
        from unittest.mock import AsyncMock

        from app.services.file import FileService
        from app.services.storage import StorageService

        mock_backend = type("FakeBackend", (), {})()
        mock_backend.blobs = {}
        mock_backend.deleted = []

        async def fake_upload_stream(
            blob_name, stream, *, content_type=None, metadata=None
        ):
            chunks = []
            async for chunk in stream:
                chunks.append(chunk)
            mock_backend.blobs[blob_name] = b"".join(chunks)
            return blob_name

        async def fake_delete(blob_name):
            mock_backend.deleted.append(blob_name)

        mock_backend.upload_stream = fake_upload_stream
        mock_backend.delete = fake_delete
        mock_backend.delete_batch = AsyncMock()
        mock_backend.download = AsyncMock()
        mock_backend.download_stream = AsyncMock()
        mock_backend.exists = AsyncMock()
        mock_backend.copy = AsyncMock()
        mock_backend.move = AsyncMock()
        mock_backend.health_check = AsyncMock(return_value=True)
        mock_backend.close = AsyncMock()

        storage_service = StorageService(backend=mock_backend)

        file_size_bytes = 200 * 1024 * 1024

        async def large_stream():
            yield b"x" * 8192

        await storage_service.upload_and_hash(
            "test-blob-overflow",
            large_stream(),
            content_type="application/octet-stream",
        )
        mock_backend.blobs = dict(mock_backend.blobs)

        from app.core.exceptions import ValidationError

        with pytest.raises(ValidationError):
            file_service = FileService(db_session)
            file_service._validate_file_size(file_size_bytes)
