from __future__ import annotations

import uuid as uuid_mod

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies.auth import get_current_user
from app.dependencies.database import get_db
from app.schemas.auth import UserResponse
from app.schemas.discovery import (
    FileMetadataUpdateRequest,
    FileTagAssignRequest,
    MessageResponse,
    SearchResponse,
    TagCreateRequest,
    TagResponse,
)
from app.services.discovery import DiscoveryService

router = APIRouter(prefix="", tags=["Discovery"])


@router.get("/search/suggestions")
async def search_suggestions(
    query: str = Query("", min_length=1),
    limit: int = Query(8, ge=1, le=20),
    current_user: UserResponse = Depends(get_current_user),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> dict:
    service = DiscoveryService(db)
    suggestions = await service.suggestions(current_user.id, query, limit)
    return {"suggestions": suggestions}


@router.get("/search", response_model=SearchResponse)
async def search(
    query: str = Query(""),
    extension: str | None = None,
    mime_type: str | None = None,
    folder_id: str | None = None,
    min_size: int | None = None,
    max_size: int | None = None,
    tag_id: str | None = None,
    favorite_only: bool = False,
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    current_user: UserResponse = Depends(get_current_user),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> SearchResponse:
    service = DiscoveryService(db)
    filters = {}
    if query:
        filters["query"] = query
    if extension:
        filters["extension"] = extension
    if mime_type:
        filters["mime_type"] = mime_type
    if folder_id:
        filters["folder_id"] = uuid_mod.UUID(folder_id)
    if min_size is not None:
        filters["min_size"] = min_size
    if max_size is not None:
        filters["max_size"] = max_size
    if tag_id:
        filters["tag_id"] = uuid_mod.UUID(tag_id)
    if favorite_only:
        filters["favorite_only"] = True
    return await service.search(current_user.id, offset=offset, limit=limit, **filters)


@router.post("/tags", response_model=TagResponse, status_code=201)
async def create_tag(
    request_data: TagCreateRequest,
    current_user: UserResponse = Depends(get_current_user),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> TagResponse:
    service = DiscoveryService(db)
    return await service.create_tag(current_user.id, request_data.name)


@router.get("/tags", response_model=list[TagResponse])
async def list_tags(
    current_user: UserResponse = Depends(get_current_user),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> list[TagResponse]:
    service = DiscoveryService(db)
    return await service.list_tags(current_user.id)


@router.delete("/tags/{tag_id}", response_model=MessageResponse)
async def delete_tag(
    tag_id: str,
    current_user: UserResponse = Depends(get_current_user),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> MessageResponse:
    service = DiscoveryService(db)
    await service.delete_tag(uuid_mod.UUID(tag_id), current_user.id)
    return MessageResponse(success=True, message="Tag deleted", code="TAG_DELETED")


@router.post("/files/{file_id}/tags", response_model=MessageResponse)
async def assign_tag(
    file_id: str,
    request_data: FileTagAssignRequest,
    current_user: UserResponse = Depends(get_current_user),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> MessageResponse:
    service = DiscoveryService(db)
    await service.assign_tag(uuid_mod.UUID(file_id), request_data.tag_id, current_user.id)
    return MessageResponse(success=True, message="Tag assigned", code="TAG_ASSIGNED")


@router.delete("/files/{file_id}/tags/{tag_id}", response_model=MessageResponse)
async def remove_tag(
    file_id: str,
    tag_id: str,
    current_user: UserResponse = Depends(get_current_user),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> MessageResponse:
    service = DiscoveryService(db)
    await service.remove_tag(uuid_mod.UUID(file_id), uuid_mod.UUID(tag_id), current_user.id)
    return MessageResponse(success=True, message="Tag removed", code="TAG_REMOVED")


@router.post("/favorites/{file_id}", status_code=201)
async def add_favorite(
    file_id: str,
    current_user: UserResponse = Depends(get_current_user),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> dict:
    service = DiscoveryService(db)
    fav = await service.add_favorite(current_user.id, uuid_mod.UUID(file_id))
    return fav.model_dump()


@router.delete("/favorites/{file_id}", response_model=MessageResponse)
async def remove_favorite(
    file_id: str,
    current_user: UserResponse = Depends(get_current_user),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> MessageResponse:
    service = DiscoveryService(db)
    await service.remove_favorite(current_user.id, uuid_mod.UUID(file_id))
    return MessageResponse(success=True, message="Favorite removed", code="FAVORITE_REMOVED")


@router.get("/favorites")
async def list_favorites(
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    current_user: UserResponse = Depends(get_current_user),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> dict:
    service = DiscoveryService(db)
    items, total = await service.list_favorites(current_user.id, offset=offset, limit=limit)
    return {"favorites": [i.model_dump() for i in items], "total": total, "offset": offset, "limit": limit}


@router.get("/recent")
async def list_recent(
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    current_user: UserResponse = Depends(get_current_user),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> dict:
    service = DiscoveryService(db)
    items, total = await service.list_recent(current_user.id, offset=offset, limit=limit)
    return {"recent": [i.model_dump() for i in items], "total": total, "offset": offset, "limit": limit}


@router.patch("/files/{file_id}/metadata")
async def update_file_metadata(
    file_id: str,
    request_data: FileMetadataUpdateRequest,
    current_user: UserResponse = Depends(get_current_user),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> dict:
    service = DiscoveryService(db)
    kwargs = {k: v for k, v in request_data.model_dump().items() if v is not None}
    return await service.update_metadata(uuid_mod.UUID(file_id), current_user.id, **kwargs)
