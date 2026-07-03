from __future__ import annotations

import uuid
from collections.abc import AsyncIterator

from fastapi import UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AuthorizationError, NotFoundError, StorageError, ValidationError
from app.core.logging_config import get_logger
from app.models.file import File
from app.repositories.discovery import RecentFileRepository
from app.repositories.file import FileRepository
from app.repositories.versioning import FileVersionRepository
from app.schemas.file import FileMetadataResponse
from app.services.audit import AuditService
from app.services.storage import StorageService

logger = get_logger(__name__)


class FileService:
    def __init__(
        self, session: AsyncSession, storage_service: StorageService | None = None,
    ) -> None:
        self.repo = FileRepository(session)
        self.version_repo = FileVersionRepository(session)
        self.recent_repo = RecentFileRepository(session)
        self.storage = storage_service or StorageService()
        self.audit = AuditService()
        self.session = session

    def _validate_filename(self, filename: str) -> str:
        if not filename or len(filename) > 1024:
            raise ValidationError("Invalid filename length")
        if "/" in filename or "\\" in filename:
            raise ValidationError("Filename contains invalid characters")
        return filename.strip()

    def _validate_extension(self, filename: str) -> str | None:
        if "." not in filename:
            return None
        ext = filename.rsplit(".", 1)[-1].lower()
        from app.config.settings import settings
        allowed = settings.ALLOWED_UPLOAD_EXTENSIONS
        if allowed is not None and ext not in allowed:
            raise ValidationError(f"File extension '.{ext}' is not allowed")
        return ext

    def _validate_mime_type(self, content_type: str | None) -> str | None:
        if content_type is None:
            return None
        if "\x00" in content_type:
            raise ValidationError("Invalid MIME type")
        return content_type.lower().strip()

    def _validate_file_size(self, size: int) -> None:
        from app.config.settings import settings
        max_bytes = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
        if size > max_bytes:
            raise ValidationError(f"File size exceeds maximum allowed size of {settings.MAX_UPLOAD_SIZE_MB}MB")

    async def _cleanup_blob(self, blob_name: str) -> None:
        try:
            await self.storage.delete_blob(blob_name)
        except Exception as exc:
            logger.error("compensation_delete_failed", blob_name=blob_name, error=str(exc))

    async def _get_file_or_raise(self, file_id: uuid.UUID, user_id: uuid.UUID) -> File:
        file_record = await self.repo.get_by_id_with_access(file_id, user_id)
        if file_record is None:
            raise NotFoundError("File", str(file_id))
        return file_record

    async def _get_file_with_role(self, file_id: uuid.UUID, user_id: uuid.UUID,
                                   min_role: str) -> File:
        from app.dependencies.permission import _ROLE_HIERARCHY, _get_effective_role

        file_record = await self._get_file_or_raise(file_id, user_id)
        effective = await _get_effective_role(self.session, user_id, "file", file_id)
        if effective is None or _ROLE_HIERARCHY.get(effective, 0) < _ROLE_HIERARCHY.get(min_role, 0):
            raise AuthorizationError("Insufficient permissions for this operation")
        return file_record

    async def upload(self, file: UploadFile, owner_id: uuid.UUID, folder_id: uuid.UUID | None = None,
                     *, trace_id: str = "") -> FileMetadataResponse:
        filename = self._validate_filename(file.filename or "unnamed")
        extension = self._validate_extension(filename)
        content_type = self._validate_mime_type(file.content_type)
        if file.size is not None and file.size > 0:
            self._validate_file_size(file.size)
        blob_name = self.storage.generate_blob_name(owner_id)
        async def _file_stream() -> AsyncIterator[bytes]:
            while True:
                chunk = await file.read(4 * 1024 * 1024)
                if not chunk:
                    break
                yield chunk
        try:
            file_size, checksum = await self.storage.upload_and_hash(
                blob_name=blob_name, stream=_file_stream(), content_type=content_type)
        except StorageError:
            raise
        except Exception as exc:
            logger.error("upload_failed", error=str(exc))
            raise StorageError("Failed to upload file") from exc
        try:
            self._validate_file_size(file_size)
        except ValidationError:
            await self._cleanup_blob(blob_name)
            raise

        existing = await self.repo.find_by_name(owner_id, folder_id, filename)
        if existing is not None:
            file_record = existing
            new_ver = (await self.version_repo.get_max_version_number(file_record.id)) + 1
            logger.info(
                "existing_file_found_creating_new_version",
                file_id=str(file_record.id),
                filename=filename,
                new_version_number=new_ver,
            )
            version = await self.version_repo.create(
                file_id=file_record.id, version_number=new_ver, blob_name=blob_name,
                checksum_sha256=checksum, file_size_bytes=file_size,
                created_by=owner_id, mime_type=content_type, extension=extension)
            await self.version_repo.set_current(file_record.id, version.id)
            await self.session.refresh(version)
            file_record.original_filename = filename
            file_record.stored_blob_name = blob_name
            file_record.mime_type = content_type
            file_record.extension = extension
            file_record.checksum_sha256 = checksum
            file_record.file_size_bytes = file_size
            file_record.version_number = new_ver
            self.session.add(file_record)
            await self.session.flush()
            logger.info(
                "new_version_created",
                file_id=str(file_record.id),
                version_number=new_ver,
            )
        else:
            try:
                file_record = await self.repo.create(
                    owner_id=owner_id, folder_id=folder_id, original_filename=filename,
                    stored_blob_name=blob_name, mime_type=content_type, extension=extension,
                    checksum_sha256=checksum, file_size_bytes=file_size)
            except Exception:
                await self._cleanup_blob(blob_name)
                raise StorageError("Failed to save file metadata") from None
            version = await self.version_repo.create(
                file_id=file_record.id, version_number=1, blob_name=blob_name,
                checksum_sha256=checksum, file_size_bytes=file_size,
                created_by=owner_id, mime_type=content_type, extension=extension)
            await self.version_repo.set_current(file_record.id, version.id)
            await self.session.refresh(version)

        self.audit.log_upload(trace_id=trace_id, user_id=str(owner_id), file_id=str(file_record.id),
                              folder_id=str(folder_id) if folder_id else None, blob_name=blob_name,
                              filename=filename, checksum=checksum, size=file_size, mime_type=content_type)
        await self.recent_repo.record(owner_id, file_record.id, "upload")
        return FileMetadataResponse.model_validate(file_record)

    async def get_metadata(self, file_id: uuid.UUID, user_id: uuid.UUID) -> FileMetadataResponse:
        return FileMetadataResponse.model_validate(await self._get_file_or_raise(file_id, user_id))

    async def download_stream(self, file_id: uuid.UUID, user_id: uuid.UUID, *, trace_id: str = ""
                              ) -> tuple[AsyncIterator[bytes], File]:
        file_record = await self._get_file_or_raise(file_id, user_id)
        stream = self.storage.download_stream(file_record.stored_blob_name)
        self.audit.log_download(trace_id=trace_id, user_id=str(user_id), file_id=str(file_id),
                                blob_name=file_record.stored_blob_name, filename=file_record.original_filename)
        await self.recent_repo.record(user_id, file_id, "download")
        return stream, file_record

    async def list_files(self, owner_id: uuid.UUID, folder_id: uuid.UUID | None = None,
                         *, offset: int = 0, limit: int = 50) -> tuple[list[FileMetadataResponse], int]:
        files, total = await self.repo.list_files(owner_id, folder_id=folder_id, offset=offset, limit=limit)
        return [FileMetadataResponse.model_validate(f) for f in files], total

    async def delete(self, file_id: uuid.UUID, user_id: uuid.UUID, *, trace_id: str = "") -> None:
        file_record = await self._get_file_with_role(file_id, user_id, "editor")
        blob_name = file_record.stored_blob_name
        await self.repo.soft_delete(file_record)
        try:
            await self.storage.delete_blob(blob_name)
        except Exception as exc:
            logger.error("blob_delete_failed_after_soft_delete", file_id=str(file_id),
                         blob_name=blob_name, error=str(exc))
        self.audit.log_delete(trace_id=trace_id, user_id=str(user_id), file_id=str(file_id),
                              blob_name=blob_name, filename=file_record.original_filename)

    async def move(self, file_id: uuid.UUID, user_id: uuid.UUID, new_folder_id: uuid.UUID | None,
                   *, trace_id: str = "") -> FileMetadataResponse:
        file_record = await self._get_file_with_role(file_id, user_id, "editor")
        updated = await self.repo.move(file_record, new_folder_id)
        await self.recent_repo.record(user_id, file_id, "move")
        return FileMetadataResponse.model_validate(updated)

    async def copy(self, file_id: uuid.UUID, user_id: uuid.UUID, target_folder_id: uuid.UUID | None,
                   *, trace_id: str = "") -> FileMetadataResponse:
        file_record = await self._get_file_with_role(file_id, user_id, "editor")
        new_blob_name = self.storage.generate_blob_name(user_id)
        try:
            backend = await self.storage._get_backend()
            await backend.copy(file_record.stored_blob_name, new_blob_name)
        except Exception as exc:
            logger.error("file_copy_blob_failed", error=str(exc))
            raise StorageError("Failed to copy file") from exc
        new_record = await self.repo.create(
            owner_id=user_id, folder_id=target_folder_id,
            original_filename=file_record.original_filename, stored_blob_name=new_blob_name,
            mime_type=file_record.mime_type, extension=file_record.extension,
            checksum_sha256=file_record.checksum_sha256, file_size_bytes=file_record.file_size_bytes)
        return FileMetadataResponse.model_validate(new_record)

    async def restore(self, file_id: uuid.UUID, user_id: uuid.UUID, *, trace_id: str = "") -> FileMetadataResponse:
        file_record = await self.repo.get_by_id(file_id, user_id, include_deleted=True)
        if file_record is None:
            raise NotFoundError("File", str(file_id))
        if not file_record.is_deleted:
            raise ValidationError("File is not in trash")
        await self.repo.restore(file_record)
        return FileMetadataResponse.model_validate(file_record)

    async def permanent_delete(self, file_id: uuid.UUID, user_id: uuid.UUID, *, trace_id: str = "") -> None:
        file_record = await self.repo.get_by_id(file_id, user_id, include_deleted=True)
        if file_record is None:
            raise NotFoundError("File", str(file_id))
        blob_name = file_record.stored_blob_name
        await self.repo.permanent_delete(file_record)
        try:
            await self.storage.delete_blob(blob_name)
        except Exception as exc:
            logger.error("permanent_delete_blob_cleanup_failed", blob_name=blob_name, error=str(exc))

    async def rename(self, file_id: uuid.UUID, user_id: uuid.UUID, new_name: str, *, trace_id: str = ""
                     ) -> FileMetadataResponse:
        file_record = await self._get_file_with_role(file_id, user_id, "editor")
        validated = self._validate_filename(new_name)
        file_record.original_filename = validated
        file_record.extension = self._validate_extension(validated)
        self.session.add(file_record)
        await self.session.flush()
        await self.recent_repo.record(user_id, file_id, "rename")
        return FileMetadataResponse.model_validate(file_record)

    async def list_trash(self, owner_id: uuid.UUID, *, offset: int = 0, limit: int = 50
                         ) -> tuple[list[FileMetadataResponse], int]:
        files, total = await self.repo.list_trash(owner_id, offset=offset, limit=limit)
        return [FileMetadataResponse.model_validate(f) for f in files], total
