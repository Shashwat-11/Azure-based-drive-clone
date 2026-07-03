from __future__ import annotations

import uuid as uuid_mod

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies.auth import get_current_user
from app.dependencies.database import get_db
from app.schemas.auth import UserResponse
from app.schemas.sharing import (
    LinkCreateRequest,
    LinkResponse,
    LinkUpdateRequest,
    MessageResponse,
    PermissionResponse,
    ResourcePermissionsResponse,
    SharedWithMeResponse,
    ShareRequest,
    TransferOwnershipRequest,
)
from app.services.sharing import LinkService, PermissionService

router = APIRouter(prefix="/collaboration", tags=["Collaboration"])


def _get_trace_id(request: Request) -> str:
    return getattr(request.state, "trace_id", "")


@router.post("/share/{resource_type}/{resource_id}", response_model=PermissionResponse)
async def share_resource(
    resource_type: str,
    resource_id: str,
    request_data: ShareRequest,
    current_user: UserResponse = Depends(get_current_user),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
    request: Request = None,  # noqa: B008
) -> PermissionResponse:
    trace_id = _get_trace_id(request) if request else ""
    service = PermissionService(db)
    return await service.share(
        resource_type, uuid_mod.UUID(resource_id), current_user.id, request_data, trace_id=trace_id
    )


@router.get("/permissions/{resource_type}/{resource_id}", response_model=ResourcePermissionsResponse)
async def get_resource_permissions(
    resource_type: str,
    resource_id: str,
    current_user: UserResponse = Depends(get_current_user),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> ResourcePermissionsResponse:
    service = PermissionService(db)
    return await service.get_resource_permissions(resource_type, uuid_mod.UUID(resource_id), current_user.id)


@router.patch("/permissions/{perm_id}", response_model=PermissionResponse)
async def update_permission(
    perm_id: str,
    request_data: ShareRequest,
    current_user: UserResponse = Depends(get_current_user),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> PermissionResponse:
    service = PermissionService(db)
    return await service.update_permission(uuid_mod.UUID(perm_id), current_user.id, request_data.role)


@router.delete("/permissions/{perm_id}", response_model=MessageResponse)
async def remove_permission(
    perm_id: str,
    current_user: UserResponse = Depends(get_current_user),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> MessageResponse:
    service = PermissionService(db)
    await service.remove_permission(uuid_mod.UUID(perm_id), current_user.id)
    return MessageResponse(success=True, message="Permission removed", code="PERMISSION_REMOVED")


@router.get("/shared-with-me", response_model=SharedWithMeResponse)
async def shared_with_me(
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    current_user: UserResponse = Depends(get_current_user),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> SharedWithMeResponse:
    service = PermissionService(db)
    items, total = await service.get_shared_with_me(current_user.id, offset=offset, limit=limit)
    return SharedWithMeResponse(items=items, total=total, offset=offset, limit=limit)


@router.get("/shared-by-me", response_model=SharedWithMeResponse)
async def shared_by_me(
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    current_user: UserResponse = Depends(get_current_user),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> SharedWithMeResponse:
    service = PermissionService(db)
    items, total = await service.get_shared_by_me(current_user.id, offset=offset, limit=limit)
    return SharedWithMeResponse(items=items, total=total, offset=offset, limit=limit)


@router.post("/transfer-ownership/{resource_type}/{resource_id}", response_model=MessageResponse)
async def transfer_ownership(
    resource_type: str,
    resource_id: str,
    request_data: TransferOwnershipRequest,
    current_user: UserResponse = Depends(get_current_user),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
    request: Request = None,  # noqa: B008
) -> MessageResponse:
    trace_id = _get_trace_id(request) if request else ""
    service = PermissionService(db)
    await service.transfer_ownership(
        resource_type, uuid_mod.UUID(resource_id), current_user.id, request_data.new_owner_id,
        trace_id=trace_id,
    )
    return MessageResponse(success=True, message="Ownership transferred", code="OWNERSHIP_TRANSFERRED")


@router.post("/links", response_model=LinkResponse, status_code=201)
async def create_link(
    request_data: LinkCreateRequest,
    current_user: UserResponse = Depends(get_current_user),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> LinkResponse:
    service = LinkService(db)
    return await service.create_link(
        current_user.id, request_data.resource_type, request_data.resource_id,
        is_public=request_data.is_public, password=request_data.password,
        expires_at=request_data.expires_at, max_downloads=request_data.max_downloads,
    )


@router.get("/links", response_model=list[LinkResponse])
async def list_links(
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    current_user: UserResponse = Depends(get_current_user),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> list[LinkResponse]:
    service = LinkService(db)
    links, _ = await service.list_links(current_user.id, offset=offset, limit=limit)
    return links


@router.patch("/links/{link_id}", response_model=LinkResponse)
async def update_link(
    link_id: str,
    request_data: LinkUpdateRequest,
    current_user: UserResponse = Depends(get_current_user),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> LinkResponse:
    kwargs = {}
    if request_data.is_public is not None:
        kwargs["is_public"] = request_data.is_public
    if request_data.password is not None:
        kwargs["password"] = request_data.password
    if request_data.expires_at is not None:
        kwargs["expires_at"] = request_data.expires_at
    if request_data.max_downloads is not None:
        kwargs["max_downloads"] = request_data.max_downloads
    if request_data.is_enabled is not None:
        kwargs["is_enabled"] = request_data.is_enabled
    service = LinkService(db)
    return await service.update_link(uuid_mod.UUID(link_id), current_user.id, **kwargs)


@router.delete("/links/{link_id}", response_model=MessageResponse)
async def delete_link(
    link_id: str,
    current_user: UserResponse = Depends(get_current_user),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> MessageResponse:
    service = LinkService(db)
    await service.delete_link(uuid_mod.UUID(link_id), current_user.id)
    return MessageResponse(success=True, message="Link revoked", code="LINK_REVOKED")
