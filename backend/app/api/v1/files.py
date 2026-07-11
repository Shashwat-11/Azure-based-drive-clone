from __future__ import annotations

import uuid as uuid_mod

from fastapi import APIRouter, Depends, Header, Query, Request, UploadFile
from fastapi import File as FastAPIFile
from fastapi.responses import Response, StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1._common import get_trace_id, parse_uuid
from app.dependencies.auth import get_current_user
from app.dependencies.database import get_db
from app.dependencies.storage import get_storage_service
from app.schemas.auth import UserResponse
from app.schemas.file import (
    CopyRequest,
    FileListResponse,
    FileMetadataResponse,
    FileUploadResponse,
    MessageResponse,
    MoveRequest,
    RenameRequest,
)
from app.services.file import FileService
from app.services.storage import StorageService

router = APIRouter(prefix="/files", tags=["Files"])


@router.post("/upload", response_model=FileUploadResponse, status_code=201)
async def upload_file(
    file: UploadFile = FastAPIFile(...),  # noqa: B008
    folder_id: str | None = None,
    current_user: UserResponse = Depends(get_current_user),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
    storage: StorageService = Depends(get_storage_service),  # noqa: B008
    request: Request = None,  # noqa: B008
) -> FileUploadResponse:
    folder_uuid = parse_uuid(folder_id)
    trace_id = get_trace_id(request) if request else ""
    service = FileService(db, storage_service=storage)
    return await service.upload(file, current_user.id, folder_id=folder_uuid, trace_id=trace_id)


@router.get("", response_model=FileListResponse)
async def list_files(
    folder_id: str | None = Query(None),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    current_user: UserResponse = Depends(get_current_user),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> FileListResponse:
    service = FileService(db)
    files, total = await service.list_files(
        current_user.id, folder_id=parse_uuid(folder_id), offset=offset, limit=limit
    )
    return FileListResponse(files=files, total=total, offset=offset, limit=limit)


@router.get("/{file_id}", response_model=FileMetadataResponse)
async def get_file(
    file_id: str,
    current_user: UserResponse = Depends(get_current_user),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> FileMetadataResponse:
    return await FileService(db).get_metadata(uuid_mod.UUID(file_id), current_user.id)


@router.get("/{file_id}/download")
async def download_file(
    file_id: str,
    current_user: UserResponse = Depends(get_current_user),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
    storage: StorageService = Depends(get_storage_service),  # noqa: B008
    request: Request = None,  # noqa: B008
    if_none_match: str | None = Header(None, alias="If-None-Match"),
):
    trace_id = get_trace_id(request) if request else ""
    service = FileService(db, storage_service=storage)
    stream, file_record = await service.download_stream(
        uuid_mod.UUID(file_id), current_user.id, trace_id=trace_id)
    etag_val = file_record.etag or file_record.checksum_sha256 or str(file_record.file_size_bytes)
    if if_none_match and if_none_match == etag_val:
        return Response(status_code=304)
    return StreamingResponse(
        stream,
        media_type=file_record.mime_type or "application/octet-stream",
        headers={
            "Content-Disposition": f'attachment; filename="{file_record.original_filename}"',
            "Content-Length": str(file_record.file_size_bytes),
            "X-Checksum-SHA256": file_record.checksum_sha256 or "",
            "ETag": etag_val,
            "Cache-Control": "private, max-age=3600",
        },
    )


@router.delete("/{file_id}", response_model=MessageResponse)
async def delete_file(
    file_id: str,
    current_user: UserResponse = Depends(get_current_user),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
    storage: StorageService = Depends(get_storage_service),  # noqa: B008
    request: Request = None,  # noqa: B008
) -> MessageResponse:
    trace_id = get_trace_id(request) if request else ""
    await FileService(db, storage_service=storage).delete(uuid_mod.UUID(file_id), current_user.id, trace_id=trace_id)
    return MessageResponse(success=True, message="File moved to trash", code="FILE_DELETED")


@router.post("/{file_id}/move", response_model=FileMetadataResponse)
async def move_file(
    file_id: str,
    move_req: MoveRequest,
    current_user: UserResponse = Depends(get_current_user),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> FileMetadataResponse:
    return await FileService(db).move(uuid_mod.UUID(file_id), current_user.id, move_req.target_parent_id)


@router.post("/{file_id}/copy", response_model=FileMetadataResponse, status_code=201)
async def copy_file(
    file_id: str,
    copy_req: CopyRequest,
    current_user: UserResponse = Depends(get_current_user),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
    storage: StorageService = Depends(get_storage_service),  # noqa: B008
    request: Request = None,  # noqa: B008
) -> FileMetadataResponse:
    trace_id = get_trace_id(request) if request else ""
    return await FileService(db, storage_service=storage).copy(
        uuid_mod.UUID(file_id), current_user.id, copy_req.target_parent_id, trace_id=trace_id
    )


@router.post("/{file_id}/restore", response_model=FileMetadataResponse)
async def restore_file(
    file_id: str,
    current_user: UserResponse = Depends(get_current_user),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> FileMetadataResponse:
    return await FileService(db).restore(uuid_mod.UUID(file_id), current_user.id)


@router.delete("/{file_id}/permanent", response_model=MessageResponse)
async def permanent_delete_file(
    file_id: str,
    current_user: UserResponse = Depends(get_current_user),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
    storage: StorageService = Depends(get_storage_service),  # noqa: B008
) -> MessageResponse:
    await FileService(db, storage_service=storage).permanent_delete(uuid_mod.UUID(file_id), current_user.id)
    return MessageResponse(success=True, message="File permanently deleted", code="FILE_PERMANENTLY_DELETED")


@router.post("/{file_id}/rename", response_model=FileMetadataResponse)
async def rename_file(
    file_id: str,
    rename_req: RenameRequest,
    current_user: UserResponse = Depends(get_current_user),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> FileMetadataResponse:
    return await FileService(db).rename(uuid_mod.UUID(file_id), current_user.id, rename_req.name)
