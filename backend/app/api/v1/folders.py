from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1._common import get_trace_id, parse_uuid
from app.dependencies.auth import get_current_user
from app.dependencies.database import get_db
from app.dependencies.storage import get_storage_service
from app.schemas.auth import UserResponse
from app.schemas.file import (
    BreadcrumbResponse,
    CopyRequest,
    FolderCreateRequest,
    FolderListResponse,
    FolderResponse,
    FolderSizeResponse,
    FolderUpdateRequest,
    MessageResponse,
    MoveRequest,
    RenameRequest,
    TrashListResponse,
    TreeResponse,
)
from app.services.file import FileService
from app.services.folder import FolderService
from app.services.storage import StorageService

router = APIRouter(prefix="/folders", tags=["Folders"])


@router.post("", response_model=FolderResponse, status_code=201)
async def create_folder(
    request_data: FolderCreateRequest,
    current_user: UserResponse = Depends(get_current_user),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
    request: Request = None,  # noqa: B008
) -> FolderResponse:
    trace_id = get_trace_id(request) if request else ""
    return await FolderService(db).create(current_user.id, request_data, trace_id=trace_id)


@router.get("", response_model=FolderListResponse)
async def list_folders(
    parent_id: str | None = Query(None),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    current_user: UserResponse = Depends(get_current_user),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> FolderListResponse:
    service = FolderService(db)
    folders, total = await service.list_folders(
        current_user.id, parent_id=parse_uuid(parent_id), offset=offset, limit=limit
    )
    return FolderListResponse(folders=folders, total=total, offset=offset, limit=limit)


@router.get("/{folder_id}", response_model=FolderResponse)
async def get_folder(
    folder_id: str,
    current_user: UserResponse = Depends(get_current_user),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> FolderResponse:
    from uuid import UUID
    return await FolderService(db).get(UUID(folder_id), current_user.id)


@router.patch("/{folder_id}", response_model=FolderResponse)
async def update_folder(
    folder_id: str,
    request_data: FolderUpdateRequest,
    current_user: UserResponse = Depends(get_current_user),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> FolderResponse:
    from uuid import UUID
    return await FolderService(db).update(UUID(folder_id), current_user.id, request_data)


@router.delete("/{folder_id}", response_model=MessageResponse)
async def delete_folder(
    folder_id: str,
    current_user: UserResponse = Depends(get_current_user),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
    request: Request = None,  # noqa: B008
) -> MessageResponse:
    from uuid import UUID
    trace_id = get_trace_id(request) if request else ""
    await FolderService(db).delete(UUID(folder_id), current_user.id, trace_id=trace_id)
    return MessageResponse(success=True, message="Folder moved to trash", code="FOLDER_DELETED")


@router.post("/{folder_id}/move", response_model=FolderResponse)
async def move_folder(
    folder_id: str,
    move_req: MoveRequest,
    current_user: UserResponse = Depends(get_current_user),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
    request: Request = None,  # noqa: B008
) -> FolderResponse:
    from uuid import UUID
    trace_id = get_trace_id(request) if request else ""
    return await FolderService(db).move(UUID(folder_id), current_user.id, move_req.target_parent_id, trace_id=trace_id)


@router.post("/{folder_id}/copy", response_model=FolderResponse, status_code=201)
async def copy_folder(
    folder_id: str,
    copy_req: CopyRequest,
    current_user: UserResponse = Depends(get_current_user),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
    storage: StorageService = Depends(get_storage_service),  # noqa: B008
    request: Request = None,  # noqa: B008
) -> FolderResponse:
    from uuid import UUID
    trace_id = get_trace_id(request) if request else ""
    return await FolderService(db, storage_service=storage).copy(
        UUID(folder_id), current_user.id, copy_req.target_parent_id, trace_id=trace_id
    )


@router.post("/{folder_id}/restore", response_model=FolderResponse)
async def restore_folder(
    folder_id: str,
    current_user: UserResponse = Depends(get_current_user),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
    request: Request = None,  # noqa: B008
) -> FolderResponse:
    from uuid import UUID
    trace_id = get_trace_id(request) if request else ""
    return await FolderService(db).restore(UUID(folder_id), current_user.id, trace_id=trace_id)


@router.delete("/{folder_id}/permanent", response_model=MessageResponse)
async def permanent_delete_folder(
    folder_id: str,
    current_user: UserResponse = Depends(get_current_user),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
    storage: StorageService = Depends(get_storage_service),  # noqa: B008
    request: Request = None,  # noqa: B008
) -> MessageResponse:
    from uuid import UUID
    trace_id = get_trace_id(request) if request else ""
    await FolderService(db, storage_service=storage).permanent_delete(
        UUID(folder_id), current_user.id, trace_id=trace_id
    )
    return MessageResponse(success=True, message="Folder permanently deleted", code="FOLDER_PERMANENTLY_DELETED")


@router.get("/{folder_id}/breadcrumbs", response_model=BreadcrumbResponse)
async def get_breadcrumbs(
    folder_id: str,
    current_user: UserResponse = Depends(get_current_user),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> BreadcrumbResponse:
    from uuid import UUID
    crumbs = await FolderService(db).get_breadcrumbs(UUID(folder_id), current_user.id)
    return BreadcrumbResponse(breadcrumbs=crumbs)


@router.get("/{folder_id}/size", response_model=FolderSizeResponse)
async def get_folder_size(
    folder_id: str,
    current_user: UserResponse = Depends(get_current_user),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> FolderSizeResponse:
    from uuid import UUID
    size_info = await FolderService(db).get_folder_size(UUID(folder_id), current_user.id)
    return FolderSizeResponse(**size_info)


@router.get("/{folder_id}/children", response_model=TreeResponse)
async def get_folder_children(
    folder_id: str,
    current_user: UserResponse = Depends(get_current_user),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> TreeResponse:
    from uuid import UUID
    items = await FolderService(db).get_tree(current_user.id, root_id=UUID(folder_id))
    return TreeResponse(items=items)


@router.post("/{folder_id}/rename", response_model=FolderResponse)
async def rename_folder(
    folder_id: str,
    rename_req: RenameRequest,
    current_user: UserResponse = Depends(get_current_user),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> FolderResponse:
    from uuid import UUID
    return await FolderService(db).rename(UUID(folder_id), current_user.id, rename_req.name)


@router.get("/trash/all", response_model=TrashListResponse)
async def list_trash(
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    current_user: UserResponse = Depends(get_current_user),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> TrashListResponse:
    service = FolderService(db)
    folders, ft = await service.list_trash(current_user.id, offset=offset, limit=limit)
    files, fit = await FileService(db).list_trash(current_user.id, offset=offset, limit=limit)
    items = [{"type": "folder", **f.model_dump()} for f in folders]
    items += [{"type": "file", **f.model_dump()} for f in files]
    return TrashListResponse(items=items, total=ft + fit, offset=offset, limit=limit)


@router.post("/trash/empty", response_model=MessageResponse)
async def empty_trash(
    current_user: UserResponse = Depends(get_current_user),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
    storage: StorageService = Depends(get_storage_service),  # noqa: B008
    request: Request = None,  # noqa: B008
) -> MessageResponse:
    trace_id = get_trace_id(request) if request else ""
    count = await FolderService(db, storage_service=storage).empty_trash(
        current_user.id, trace_id=trace_id
    )
    return MessageResponse(success=True, message=f"Trash emptied ({count} items)", code="TRASH_EMPTIED")
