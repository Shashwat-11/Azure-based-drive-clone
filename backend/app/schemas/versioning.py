from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class VersionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    file_id: uuid.UUID
    version_number: int
    checksum_sha256: str
    mime_type: str | None
    extension: str | None
    file_size_bytes: int
    created_by: uuid.UUID
    etag: str | None
    previous_version_id: uuid.UUID | None
    is_current: bool
    created_at: datetime
    updated_at: datetime


class VersionListResponse(BaseModel):
    versions: list[VersionResponse]
    total: int
    offset: int
    limit: int


class MessageResponse(BaseModel):
    success: bool
    message: str
    code: str
