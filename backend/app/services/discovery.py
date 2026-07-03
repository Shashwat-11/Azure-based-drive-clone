from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.core.logging_config import get_logger
from app.repositories.discovery import (
    FavoriteRepository,
    RecentFileRepository,
    SearchRepository,
    TagRepository,
)
from app.repositories.file import FileRepository
from app.schemas.discovery import (
    FavoriteResponse,
    RecentFileResponse,
    SearchResponse,
    TagResponse,
)

logger = get_logger(__name__)


class DiscoveryService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.search_repo = SearchRepository(session)
        self.tag_repo = TagRepository(session)
        self.fav_repo = FavoriteRepository(session)
        self.recent_repo = RecentFileRepository(session)
        self.file_repo = FileRepository(session)

    async def search(self, user_id: uuid.UUID, *, offset: int = 0, limit: int = 50, **filters
                     ) -> SearchResponse:
        files, total = await self.search_repo.search(user_id=user_id, offset=offset, limit=limit, **filters)
        items = [{
            "id": str(f.id), "owner_id": str(f.owner_id), "folder_id": str(f.folder_id) if f.folder_id else None,
            "original_filename": f.original_filename, "mime_type": f.mime_type,
            "extension": f.extension, "checksum_sha256": f.checksum_sha256,
            "file_size_bytes": f.file_size_bytes, "version_number": f.version_number,
            "created_at": str(f.created_at), "updated_at": str(f.updated_at),
        } for f in files]
        return SearchResponse(files=items, total=total, offset=offset, limit=limit)

    async def suggestions(self, user_id: uuid.UUID, prefix: str, limit: int = 8
                          ) -> list[str]:
        file_suggestions = await self.search_repo.suggest(user_id, prefix, limit)
        tag_suggestions = await self.tag_repo.suggest(user_id, prefix, limit)
        combined = list(dict.fromkeys(file_suggestions + tag_suggestions))
        return combined[:limit]

    async def create_tag(self, user_id: uuid.UUID, name: str) -> TagResponse:
        existing = await self.tag_repo.get_by_name(user_id, name)
        if existing is not None:
            return TagResponse.model_validate(existing)
        tag = await self.tag_repo.create(user_id, name)
        return TagResponse.model_validate(tag)

    async def list_tags(self, user_id: uuid.UUID) -> list[TagResponse]:
        tags = await self.tag_repo.list_by_user(user_id)
        return [TagResponse.model_validate(t) for t in tags]

    async def delete_tag(self, tag_id: uuid.UUID, user_id: uuid.UUID) -> None:
        tag = await self.tag_repo.get_by_id(tag_id)
        if tag is None or tag.user_id != user_id:
            raise NotFoundError("Tag", str(tag_id))
        await self.tag_repo.delete(tag)

    async def assign_tag(self, file_id: uuid.UUID, tag_id: uuid.UUID, user_id: uuid.UUID) -> None:
        file_record = await self.file_repo.get_by_id_with_access(file_id, user_id)
        if file_record is None:
            raise NotFoundError("File", str(file_id))
        tag = await self.tag_repo.get_by_id(tag_id)
        if tag is None:
            raise NotFoundError("Tag", str(tag_id))
        await self.tag_repo.assign_to_file(file_id, tag_id)

    async def remove_tag(self, file_id: uuid.UUID, tag_id: uuid.UUID, user_id: uuid.UUID) -> None:
        file_record = await self.file_repo.get_by_id_with_access(file_id, user_id)
        if file_record is None:
            raise NotFoundError("File", str(file_id))
        await self.tag_repo.remove_from_file(file_id, tag_id)

    async def add_favorite(self, user_id: uuid.UUID, file_id: uuid.UUID) -> FavoriteResponse:
        file_record = await self.file_repo.get_by_id_with_access(file_id, user_id)
        if file_record is None:
            raise NotFoundError("File", str(file_id))
        fav = await self.fav_repo.add(user_id, file_id)
        return FavoriteResponse(user_id=user_id, file_id=file_id,
                                file_name=file_record.original_filename,
                                created_at=fav.created_at)

    async def remove_favorite(self, user_id: uuid.UUID, file_id: uuid.UUID) -> None:
        await self.fav_repo.remove(user_id, file_id)

    async def list_favorites(self, user_id: uuid.UUID, *, offset: int = 0, limit: int = 50
                             ) -> tuple[list[FavoriteResponse], int]:
        favs, total = await self.fav_repo.list_by_user(user_id, offset=offset, limit=limit)
        items = [FavoriteResponse(user_id=f.user_id, file_id=f.file_id,
                                  created_at=f.created_at) for f in favs]
        return items, total

    async def list_recent(self, user_id: uuid.UUID, *, offset: int = 0, limit: int = 50
                          ) -> tuple[list[RecentFileResponse], int]:
        recents, total = await self.recent_repo.list_by_user(user_id, offset=offset, limit=limit)
        items = [RecentFileResponse(user_id=r.user_id, file_id=r.file_id,
                                    action_type=r.action_type,
                                    accessed_at=r.accessed_at) for r in recents]
        return items, total

    async def record_access(self, user_id: uuid.UUID, file_id: uuid.UUID, action_type: str) -> None:
        await self.recent_repo.record(user_id, file_id, action_type)

    async def update_metadata(self, file_id: uuid.UUID, user_id: uuid.UUID, **kwargs) -> dict:
        file_record = await self.file_repo.get_by_id_with_access(file_id, user_id)
        if file_record is None:
            raise NotFoundError("File", str(file_id))
        for key, value in kwargs.items():
            if value is not None and hasattr(file_record, key):
                setattr(file_record, key, value)
        self.session.add(file_record)
        await self.session.flush()
        return {"id": str(file_record.id), **{k: getattr(file_record, k) for k in kwargs}}
