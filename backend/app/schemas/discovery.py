from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class FileMetadataUpdateRequest(BaseModel):
    description: str | None = Field(None, max_length=2000)
    color_label: str | None = Field(None, max_length=20)
    custom_properties: dict | None = None


class TagResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    name: str
    created_at: datetime


class TagCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)


class FileTagAssignRequest(BaseModel):
    tag_id: uuid.UUID


class FavoriteResponse(BaseModel):
    user_id: uuid.UUID
    file_id: uuid.UUID
    file_name: str | None = None
    created_at: datetime


class RecentFileResponse(BaseModel):
    user_id: uuid.UUID
    file_id: uuid.UUID
    file_name: str | None = None
    action_type: str
    accessed_at: datetime


class SearchRequest(BaseModel):
    query: str = ""
    extension: str | None = None
    mime_type: str | None = None
    folder_id: uuid.UUID | None = None
    created_after: datetime | None = None
    created_before: datetime | None = None
    min_size: int | None = None
    max_size: int | None = None
    tag_id: uuid.UUID | None = None
    favorite_only: bool = False


class SearchResponse(BaseModel):
    files: list[dict]
    total: int
    offset: int
    limit: int


class SearchSuggestionResponse(BaseModel):
    suggestions: list[str]


class MessageResponse(BaseModel):
    success: bool
    message: str
    code: str
