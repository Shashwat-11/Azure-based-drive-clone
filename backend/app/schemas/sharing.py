from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ShareRequest(BaseModel):
    user_id: uuid.UUID
    role: str = Field(..., pattern="^(editor|viewer|commenter)$")


class PermissionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    resource_type: str
    resource_id: uuid.UUID
    role: str
    granted_by: uuid.UUID | None
    created_at: datetime
    updated_at: datetime


class ResourcePermissionsResponse(BaseModel):
    owner_id: uuid.UUID
    permissions: list[PermissionResponse]


class LinkCreateRequest(BaseModel):
    resource_type: str = Field(..., pattern="^(file|folder)$")
    resource_id: uuid.UUID
    is_public: bool = True
    password: str | None = None
    expires_at: datetime | None = None
    max_downloads: int | None = None


class LinkUpdateRequest(BaseModel):
    is_public: bool | None = None
    password: str | None = None
    expires_at: datetime | None = None
    max_downloads: int | None = None
    is_enabled: bool | None = None


class LinkResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    resource_type: str
    resource_id: uuid.UUID
    token: str
    is_public: bool
    expires_at: datetime | None
    max_downloads: int | None
    download_count: int
    is_enabled: bool
    created_by: uuid.UUID
    created_at: datetime
    updated_at: datetime

    # Never expose password_hash


class LinkAccessRequest(BaseModel):
    password: str | None = None


class TransferOwnershipRequest(BaseModel):
    new_owner_id: uuid.UUID


class SharedWithMeResponse(BaseModel):
    items: list[dict]
    total: int
    offset: int
    limit: int


class MessageResponse(BaseModel):
    success: bool
    message: str
    code: str
