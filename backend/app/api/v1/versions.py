from __future__ import annotations

import uuid as uuid_mod

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1._common import get_trace_id
from app.dependencies.auth import get_current_user
from app.dependencies.database import get_db
from app.dependencies.storage import get_storage_service
from app.repositories.versioning import FileVersionRepository
from app.schemas.auth import UserResponse
from app.schemas.versioning import MessageResponse, VersionListResponse, VersionResponse
from app.services.storage import StorageService
from app.services.versioning import VersionService

router = APIRouter(prefix="/versions", tags=["Versions"])


async def _verify_file_access(file_id: str, user_id: uuid_mod.UUID, db: AsyncSession) -> None:
    from app.core.exceptions import NotFoundError
    from app.repositories.file import FileRepository

    repo = FileRepository(db)
    file_record = await repo.get_by_id_with_access(uuid_mod.UUID(file_id), user_id)
    if file_record is None:
        raise NotFoundError("File", file_id)


async def _verify_version_access(version_id: str, user_id: uuid_mod.UUID, db: AsyncSession) -> None:
    from app.core.exceptions import NotFoundError
    from app.repositories.file import FileRepository

    ver_repo = FileVersionRepository(db)
    version = await ver_repo.get_by_id(uuid_mod.UUID(version_id))
    if version is None:
        raise NotFoundError("Version", version_id)
    file_repo = FileRepository(db)
    file_record = await file_repo.get_by_id_with_access(version.file_id, user_id)
    if file_record is None:
        raise NotFoundError("Version", version_id)


@router.get("/file/{file_id}", response_model=VersionListResponse)
async def list_file_versions(
    file_id: str,
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    current_user: UserResponse = Depends(get_current_user),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> VersionListResponse:
    await _verify_file_access(file_id, current_user.id, db)
    service = VersionService(db)
    versions, total = await service.list_versions(uuid_mod.UUID(file_id), offset=offset, limit=limit)
    return VersionListResponse(versions=versions, total=total, offset=offset, limit=limit)


@router.get("/{version_id}", response_model=VersionResponse)
async def get_version(
    version_id: str,
    current_user: UserResponse = Depends(get_current_user),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> VersionResponse:
    await _verify_version_access(version_id, current_user.id, db)
    service = VersionService(db)
    return await service.get_version(uuid_mod.UUID(version_id))


@router.get("/{version_id}/download")
async def download_version(
    version_id: str,
    current_user: UserResponse = Depends(get_current_user),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
    storage: StorageService = Depends(get_storage_service),  # noqa: B008
):
    await _verify_version_access(version_id, current_user.id, db)
    service = VersionService(db, storage_service=storage)
    version, blob_name = await service.download_version(uuid_mod.UUID(version_id), current_user.id)
    stream = storage.download_stream(blob_name)
    return StreamingResponse(
        stream,
        media_type=version.mime_type or "application/octet-stream",
        headers={
            "Content-Length": str(version.file_size_bytes),
            "X-Checksum-SHA256": version.checksum_sha256,
        },
    )


@router.post("/{version_id}/restore", response_model=VersionResponse)
async def restore_version(
    version_id: str,
    current_user: UserResponse = Depends(get_current_user),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
    storage: StorageService = Depends(get_storage_service),  # noqa: B008
    request: Request = None,  # noqa: B008
) -> VersionResponse:
    await _verify_version_access(version_id, current_user.id, db)
    trace_id = get_trace_id(request) if request else ""
    service = VersionService(db, storage_service=storage)
    return await service.restore_version(uuid_mod.UUID(version_id), current_user.id, trace_id=trace_id)


@router.delete("/{version_id}", response_model=MessageResponse)
async def delete_version(
    version_id: str,
    current_user: UserResponse = Depends(get_current_user),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> MessageResponse:
    await _verify_version_access(version_id, current_user.id, db)
    service = VersionService(db)
    await service.delete_version(uuid_mod.UUID(version_id))
    return MessageResponse(success=True, message="Version deleted", code="VERSION_DELETED")
