from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class FolderCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    parent_id: uuid.UUID | None = None


class FolderUpdateRequest(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=255)


class FolderResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    parent_id: uuid.UUID | None
    owner_id: uuid.UUID
    created_at: datetime
    updated_at: datetime


class MoveRequest(BaseModel):
    target_parent_id: uuid.UUID | None = None


class CopyRequest(BaseModel):
    target_parent_id: uuid.UUID | None = None


class RenameRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)


class FileMetadataResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    owner_id: uuid.UUID
    folder_id: uuid.UUID | None
    original_filename: str
    mime_type: str | None
    extension: str | None
    checksum_sha256: str | None
    file_size_bytes: int
    version_number: int
    created_at: datetime
    updated_at: datetime


class FileUploadResponse(FileMetadataResponse):
    pass


class FileListResponse(BaseModel):
    files: list[FileMetadataResponse]
    total: int
    offset: int
    limit: int


class FolderListResponse(BaseModel):
    folders: list[FolderResponse]
    total: int
    offset: int
    limit: int


class BreadcrumbResponse(BaseModel):
    breadcrumbs: list[FolderResponse]


class FolderSizeResponse(BaseModel):
    folder_id: uuid.UUID
    file_count: int
    folder_count: int
    total_size_bytes: int


class TreeResponse(BaseModel):
    items: list[FolderResponse]


class TrashListResponse(BaseModel):
    items: list[dict]
    total: int
    offset: int
    limit: int


class MessageResponse(BaseModel):
    success: bool
    message: str
    code: str
