from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, ValidationError
from app.core.logging_config import get_logger
from app.models.versioning import FileVersion
from app.repositories.file import FileRepository
from app.repositories.versioning import FileVersionRepository
from app.schemas.versioning import VersionResponse
from app.services.audit import AuditService
from app.services.storage import StorageService

logger = get_logger(__name__)


def _version_to_response(v: FileVersion) -> VersionResponse:
    return VersionResponse(
        id=v.id, file_id=v.file_id, version_number=v.version_number,
        checksum_sha256=v.checksum_sha256, mime_type=v.mime_type,
        extension=v.extension, file_size_bytes=v.file_size_bytes,
        created_by=v.created_by, etag=v.etag,
        previous_version_id=v.previous_version_id,
        is_current=(v.is_current if v.is_current is not None else False),
        created_at=v.created_at, updated_at=v.updated_at,
    )


class VersionService:
    def __init__(
        self, session: AsyncSession, storage_service: StorageService | None = None,
    ) -> None:
        self.repo = FileVersionRepository(session)
        self.file_repo = FileRepository(session)
        self.storage = storage_service or StorageService()
        self.audit = AuditService()
        self.session = session

    async def create_version(
        self, file_id: uuid.UUID, user_id: uuid.UUID, blob_name: str,
        checksum_sha256: str, file_size_bytes: int, *,
        mime_type: str | None = None, extension: str | None = None,
        etag: str | None = None, trace_id: str = "",
    ) -> VersionResponse:
        max_ver = await self.repo.get_max_version_number(file_id)
        new_ver_num = max_ver + 1
        version = await self.repo.create(
            file_id=file_id, version_number=new_ver_num, blob_name=blob_name,
            checksum_sha256=checksum_sha256, file_size_bytes=file_size_bytes,
            created_by=user_id, mime_type=mime_type, extension=extension, etag=etag,
        )
        await self.repo.set_current(file_id, version.id)
        logger.info("new_version_created", file_id=str(file_id), version=new_ver_num,
                     user_id=str(user_id))
        return _version_to_response(version)

    async def get_version(self, version_id: uuid.UUID) -> VersionResponse:
        version = await self.repo.get_by_id(version_id)
        if version is None:
            raise NotFoundError("Version", str(version_id))
        return _version_to_response(version)

    async def list_versions(
        self, file_id: uuid.UUID, *, offset: int = 0, limit: int = 50,
    ) -> tuple[list[VersionResponse], int]:
        versions, total = await self.repo.list_versions(file_id, offset=offset, limit=limit)
        return [_version_to_response(v) for v in versions], total

    async def download_version(
        self, version_id: uuid.UUID, user_id: uuid.UUID,
    ) -> tuple[FileVersion, str]:
        version = await self.repo.get_by_id(version_id)
        if version is None:
            raise NotFoundError("Version", str(version_id))
        return version, version.blob_name

    async def restore_version(
        self, version_id: uuid.UUID, user_id: uuid.UUID, *, trace_id: str = "",
    ) -> VersionResponse:
        source_version = await self.repo.get_by_id(version_id)
        if source_version is None:
            raise NotFoundError("Version", str(version_id))

        new_blob_name = self.storage.generate_blob_name(user_id)
        try:
            backend = await self.storage._get_backend()
            await backend.copy(source_version.blob_name, new_blob_name)
        except Exception as exc:
            logger.error("version_restore_blob_copy_failed", error=str(exc))
            raise

        new_version = await self.repo.create(
            file_id=source_version.file_id,
            version_number=(await self.repo.get_max_version_number(source_version.file_id)) + 1,
            blob_name=new_blob_name,
            checksum_sha256=source_version.checksum_sha256,
            file_size_bytes=source_version.file_size_bytes,
            created_by=user_id,
            mime_type=source_version.mime_type,
            extension=source_version.extension,
            etag=source_version.etag,
            previous_version_id=source_version.id,
        )
        await self.repo.set_current(source_version.file_id, new_version.id)
        await self.session.refresh(new_version)

        file_record = await self.file_repo.get_by_id_any(source_version.file_id)
        if file_record is not None:
            file_record.stored_blob_name = new_blob_name
            file_record.checksum_sha256 = source_version.checksum_sha256
            file_record.file_size_bytes = source_version.file_size_bytes
            file_record.mime_type = source_version.mime_type
            file_record.extension = source_version.extension
            file_record.etag = source_version.etag
            self.session.add(file_record)
            await self.session.flush()

        logger.info("version_restored", file_id=str(source_version.file_id),
                     source_version=source_version.version_number,
                     new_version=new_version.version_number)
        return _version_to_response(new_version)

    async def delete_version(self, version_id: uuid.UUID) -> None:
        version = await self.repo.get_by_id(version_id)
        if version is None:
            raise NotFoundError("Version", str(version_id))
        if version.is_current:
            raise ValidationError("Cannot delete the current version. Restore another version first.")
        total = (await self.repo.list_versions(version.file_id, limit=1))[1]
        if total <= 1:
            raise ValidationError("Cannot delete the only version of a file")
        await self.repo.soft_delete(version)
