from __future__ import annotations

import uuid

from sqlalchemy import case, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging_config import get_logger
from app.models.discovery import Favorite, FileTag, RecentFile, Tag
from app.models.file import File

logger = get_logger(__name__)


class TagRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, user_id: uuid.UUID, name: str) -> Tag:
        tag = Tag(user_id=user_id, name=name.lower().strip())
        self.session.add(tag)
        await self.session.flush()
        return tag

    async def get_by_name(self, user_id: uuid.UUID, name: str) -> Tag | None:
        result = await self.session.execute(
            select(Tag).where(Tag.user_id == user_id, Tag.name == name.lower().strip())
        )
        return result.scalar_one_or_none()

    async def get_by_id(self, tag_id: uuid.UUID) -> Tag | None:
        result = await self.session.execute(select(Tag).where(Tag.id == tag_id))
        return result.scalar_one_or_none()

    async def list_by_user(self, user_id: uuid.UUID) -> list[Tag]:
        result = await self.session.execute(
            select(Tag).where(Tag.user_id == user_id).order_by(Tag.name.asc())
        )
        return list(result.scalars().all())

    async def delete(self, tag: Tag) -> None:
        await self.session.delete(tag)
        await self.session.flush()

    async def assign_to_file(self, file_id: uuid.UUID, tag_id: uuid.UUID) -> FileTag:
        ft = FileTag(file_id=file_id, tag_id=tag_id)
        self.session.add(ft)
        await self.session.flush()
        return ft

    async def remove_from_file(self, file_id: uuid.UUID, tag_id: uuid.UUID) -> None:
        result = await self.session.execute(
            select(FileTag).where(FileTag.file_id == file_id, FileTag.tag_id == tag_id)
        )
        ft = result.scalar_one_or_none()
        if ft is not None:
            await self.session.delete(ft)
            await self.session.flush()

    async def get_tags_for_file(self, file_id: uuid.UUID) -> list[Tag]:
        result = await self.session.execute(
            select(Tag).join(FileTag, FileTag.tag_id == Tag.id)
            .where(FileTag.file_id == file_id).order_by(Tag.name.asc())
        )
        return list(result.scalars().all())

    async def suggest(self, user_id: uuid.UUID, prefix: str, limit: int = 8) -> list[str]:
        result = await self.session.execute(
            select(Tag.name).where(Tag.user_id == user_id, Tag.name.ilike(f"{prefix}%"))
            .order_by(Tag.name.asc()).limit(limit)
        )
        return [row[0] for row in result.all()]


class FavoriteRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add(self, user_id: uuid.UUID, file_id: uuid.UUID) -> Favorite:
        fav = Favorite(user_id=user_id, file_id=file_id)
        self.session.add(fav)
        await self.session.flush()
        return fav

    async def remove(self, user_id: uuid.UUID, file_id: uuid.UUID) -> None:
        result = await self.session.execute(
            select(Favorite).where(Favorite.user_id == user_id, Favorite.file_id == file_id)
        )
        fav = result.scalar_one_or_none()
        if fav is not None:
            await self.session.delete(fav)
            await self.session.flush()

    async def is_favorited(self, user_id: uuid.UUID, file_id: uuid.UUID) -> bool:
        result = await self.session.execute(
            select(Favorite.id).where(Favorite.user_id == user_id, Favorite.file_id == file_id)
        )
        return result.scalar_one_or_none() is not None

    async def list_by_user(self, user_id: uuid.UUID, *, offset: int = 0, limit: int = 50
                           ) -> tuple[list[Favorite], int]:
        base = select(Favorite).where(Favorite.user_id == user_id)
        total = (await self.session.execute(
            select(func.count()).select_from(base.subquery()))).scalar_one()
        query = base.order_by(Favorite.created_at.desc()).offset(offset).limit(limit)
        result = await self.session.execute(query)
        return list(result.scalars().all()), total


class RecentFileRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def record(self, user_id: uuid.UUID, file_id: uuid.UUID, action_type: str) -> None:
        existing = (await self.session.execute(
            select(RecentFile).where(
                RecentFile.user_id == user_id,
                RecentFile.file_id == file_id,
                RecentFile.action_type == action_type,
            )
        )).scalar_one_or_none()
        now = func.now()
        if existing is not None:
            existing.accessed_at = now
            self.session.add(existing)
        else:
            self.session.add(RecentFile(user_id=user_id, file_id=file_id, action_type=action_type))
        await self.session.flush()

    async def list_by_user(self, user_id: uuid.UUID, *, offset: int = 0, limit: int = 50
                           ) -> tuple[list[RecentFile], int]:
        base = select(RecentFile).where(RecentFile.user_id == user_id)
        total = (await self.session.execute(
            select(func.count()).select_from(base.subquery()))).scalar_one()
        query = base.order_by(RecentFile.accessed_at.desc()).offset(offset).limit(limit)
        result = await self.session.execute(query)
        return list(result.scalars().all()), total


class SearchRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def _get_accessible_file_ids(self, user_id: uuid.UUID) -> list[uuid.UUID]:
        from app.models.sharing import Permission
        from app.repositories.file import FolderRepository

        owned = await self.session.execute(
            select(File.id).where(File.owner_id == user_id, File.is_deleted == False)  # noqa: E712
        )
        owned_ids = {row[0] for row in owned.all()}

        direct_perms = await self.session.execute(
            select(Permission.resource_id).where(
                Permission.user_id == user_id, Permission.resource_type == "file"
            )
        )
        for row in direct_perms.all():
            owned_ids.add(row[0])

        folder_perms = await self.session.execute(
            select(Permission.resource_id).where(
                Permission.user_id == user_id, Permission.resource_type == "folder"
            )
        )
        folder_ids = {row[0] for row in folder_perms.all()}

        if folder_ids:
            folder_repo = FolderRepository(self.session)
            all_folder_ids = set()
            for fid in folder_ids:
                subtree = await folder_repo.get_subtree_ids(fid)
                all_folder_ids.update(subtree)
            files_in_folders = await self.session.execute(
                select(File.id).where(
                    File.folder_id.in_(all_folder_ids),
                    File.is_deleted == False,  # noqa: E712
                )
            )
            for row in files_in_folders.all():
                owned_ids.add(row[0])

        return list(owned_ids)

    async def search(
        self, user_id: uuid.UUID, *, query: str = "", extension: str | None = None,
        mime_type: str | None = None, folder_id: uuid.UUID | None = None,
        min_size: int | None = None, max_size: int | None = None,
        tag_id: uuid.UUID | None = None, favorite_only: bool = False,
        offset: int = 0, limit: int = 50,
    ) -> tuple[list[File], int]:
        accessible_ids = await self._get_accessible_file_ids(user_id)
        if not accessible_ids:
            return [], 0

        conditions = [File.id.in_(accessible_ids), File.is_deleted == False]  # noqa: E712

        if query:
            conditions.append(
                or_(
                    File.original_filename.ilike(f"%{query}%"),
                    File.description.ilike(f"%{query}%"),
                )
            )
        if extension:
            conditions.append(File.extension == extension.lower())
        if mime_type:
            conditions.append(File.mime_type.ilike(f"%{mime_type}%"))
        if folder_id is not None:
            conditions.append(File.folder_id == folder_id)
        if min_size is not None:
            conditions.append(File.file_size_bytes >= min_size)
        if max_size is not None:
            conditions.append(File.file_size_bytes <= max_size)
        if tag_id is not None:
            conditions.append(
                File.id.in_(select(FileTag.file_id).where(FileTag.tag_id == tag_id))
            )
        if favorite_only:
            conditions.append(
                File.id.in_(select(Favorite.file_id).where(Favorite.user_id == user_id))
            )

        base = select(File).where(*conditions)
        total_subquery = select(func.count()).select_from(base.subquery())
        total = (await self.session.execute(total_subquery)).scalar_one()

        if query:
            rank = case(
                (File.original_filename == query, 1),
                (File.original_filename.ilike(f"{query}%"), 2),
                (File.original_filename.ilike(f"%{query}%"), 3),
                (File.description.ilike(f"%{query}%"), 4),
                else_=5,
            ).label("rank")
            query_stmt = base.add_columns(rank).order_by("rank", File.updated_at.desc())
        else:
            query_stmt = base.order_by(File.updated_at.desc())

        query_stmt = query_stmt.offset(offset).limit(limit)
        result = await self.session.execute(query_stmt)
        files = []
        for row in result.all():
            files.append(row[0])
        return files, total

    async def suggest(self, user_id: uuid.UUID, prefix: str, limit: int = 8) -> list[str]:
        accessible_ids = await self._get_accessible_file_ids(user_id)
        if not accessible_ids:
            return []

        result = await self.session.execute(
            select(File.original_filename).where(
                File.id.in_(accessible_ids),
                File.original_filename.ilike(f"{prefix}%"),
                File.is_deleted == False,  # noqa: E712
            ).order_by(File.original_filename.asc()).limit(limit)
        )
        return list({row[0] for row in result.all()})
