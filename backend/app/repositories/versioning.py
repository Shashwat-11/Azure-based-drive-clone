from __future__ import annotations

import uuid

from sqlalchemy import case, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging_config import get_logger
from app.models.versioning import FileVersion

logger = get_logger(__name__)


class FileVersionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(
        self, file_id: uuid.UUID, version_number: int, blob_name: str,
        checksum_sha256: str, file_size_bytes: int, created_by: uuid.UUID, *,
        mime_type: str | None = None, extension: str | None = None,
        etag: str | None = None, previous_version_id: uuid.UUID | None = None,
    ) -> FileVersion:
        version = FileVersion(
            file_id=file_id, version_number=version_number, blob_name=blob_name,
            checksum_sha256=checksum_sha256, file_size_bytes=file_size_bytes,
            created_by=created_by, mime_type=mime_type, extension=extension,
            etag=etag, previous_version_id=previous_version_id, is_current=False,
        )
        self.session.add(version)
        await self.session.flush()
        logger.info("version_created", version_id=str(version.id), file_id=str(file_id),
                     version_number=version_number)
        return version

    async def set_current(self, file_id: uuid.UUID, version_id: uuid.UUID) -> None:
        """Atomically set the current version — clears old current and sets new in one UPDATE."""
        await self.session.execute(
            update(FileVersion).where(
                (FileVersion.file_id == file_id)
                & ((FileVersion.is_current == True) | (FileVersion.id == version_id))  # noqa: E712
            ).values(
                is_current=case((FileVersion.id == version_id, True), else_=False)
            )
        )
        await self.session.flush()
        logger.debug("current_version_set", version_id=str(version_id), file_id=str(file_id))

    async def get_by_id(self, version_id: uuid.UUID) -> FileVersion | None:
        result = await self.session.execute(
            select(FileVersion).where(
                FileVersion.id == version_id, FileVersion.is_deleted == False  # noqa: E712
            ).execution_options(populate_existing=True)
        )
        return result.scalar_one_or_none()

    async def get_current(self, file_id: uuid.UUID) -> FileVersion | None:
        result = await self.session.execute(
            select(FileVersion).where(
                FileVersion.file_id == file_id,
                FileVersion.is_current == True,  # noqa: E712
                FileVersion.is_deleted == False,  # noqa: E712
            )
        )
        return result.scalar_one_or_none()

    async def get_max_version_number(self, file_id: uuid.UUID) -> int:
        result = await self.session.execute(
            select(func.coalesce(func.max(FileVersion.version_number), 0))
            .where(FileVersion.file_id == file_id)
        )
        return result.scalar_one()

    async def list_versions(
        self, file_id: uuid.UUID, *, offset: int = 0, limit: int = 50,
    ) -> tuple[list[FileVersion], int]:
        base = select(FileVersion).where(
            FileVersion.file_id == file_id, FileVersion.is_deleted == False  # noqa: E712
        )
        total_q = select(func.count(FileVersion.id)).where(
            FileVersion.file_id == file_id, FileVersion.is_deleted == False  # noqa: E712
        )
        total = (await self.session.execute(total_q)).scalar_one()
        query = base.order_by(FileVersion.version_number.desc()).offset(offset).limit(limit)
        result = await self.session.execute(query)
        return list(result.scalars().all()), total

    async def soft_delete(self, version: FileVersion) -> None:
        version.is_deleted = True
        self.session.add(version)
        await self.session.flush()
        logger.info("version_deleted", version_id=str(version.id))
