from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging_config import get_logger
from app.models.file import File, Folder

logger = get_logger(__name__)


class FolderRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(
        self, name: str, owner_id: uuid.UUID, parent_id: uuid.UUID | None = None
    ) -> Folder:
        folder = Folder(name=name, owner_id=owner_id, parent_id=parent_id)
        self.session.add(folder)
        await self.session.flush()
        logger.info("folder_created", folder_id=str(folder.id), name=folder.name)
        return folder

    async def get_by_id(
        self, folder_id: uuid.UUID, owner_id: uuid.UUID, *, include_deleted: bool = False
    ) -> Folder | None:
        conditions = [Folder.id == folder_id, Folder.owner_id == owner_id]
        if not include_deleted:
            conditions.append(Folder.is_deleted == False)  # noqa: E712
        result = await self.session.execute(select(Folder).where(*conditions))
        return result.scalar_one_or_none()

    async def get_by_id_any_owner(self, folder_id: uuid.UUID) -> Folder | None:
        result = await self.session.execute(
            select(Folder).where(Folder.id == folder_id)
        )
        return result.scalar_one_or_none()

    async def list_folders(
        self,
        owner_id: uuid.UUID,
        parent_id: uuid.UUID | None = None,
        *,
        offset: int = 0,
        limit: int = 50,
    ) -> tuple[list[Folder], int]:
        base_query = select(Folder).where(
            Folder.owner_id == owner_id,
            Folder.parent_id == parent_id,
            Folder.is_deleted == False,  # noqa: E712
        )
        total_q = select(func.count(Folder.id)).where(
            Folder.owner_id == owner_id,
            Folder.parent_id == parent_id,
            Folder.is_deleted == False,  # noqa: E712
        )
        total_result = await self.session.execute(total_q)
        total = total_result.scalar_one()
        query = base_query.order_by(Folder.name.asc()).offset(offset).limit(limit)
        result = await self.session.execute(query)
        folders = list(result.scalars().all())
        return folders, total

    async def list_trash(
        self, owner_id: uuid.UUID, *, offset: int = 0, limit: int = 50
    ) -> tuple[list[Folder], int]:
        base = select(Folder).where(
            Folder.owner_id == owner_id, Folder.is_deleted == True  # noqa: E712
        )
        total_q = select(func.count()).select_from(Folder).where(
            Folder.owner_id == owner_id, Folder.is_deleted == True  # noqa: E712
        )
        total = (await self.session.execute(total_q)).scalar_one()
        query = base.order_by(Folder.deleted_at.desc().nullslast()).offset(offset).limit(limit)
        result = await self.session.execute(query)
        return list(result.scalars().all()), total

    async def update(self, folder: Folder) -> Folder:
        self.session.add(folder)
        await self.session.flush()
        logger.debug("folder_updated", folder_id=str(folder.id))
        return folder

    async def soft_delete(self, folder: Folder) -> None:
        folder.soft_delete()
        self.session.add(folder)
        await self.session.flush()
        logger.info("folder_soft_deleted", folder_id=str(folder.id))

    async def restore(self, folder: Folder) -> None:
        folder.restore()
        self.session.add(folder)
        await self.session.flush()
        logger.info("folder_restored", folder_id=str(folder.id))

    async def permanent_delete(self, folder: Folder) -> None:
        await self.session.delete(folder)
        await self.session.flush()
        logger.info("folder_permanently_deleted", folder_id=str(folder.id))

    async def exists_by_name(
        self, name: str, owner_id: uuid.UUID, parent_id: uuid.UUID | None = None
    ) -> bool:
        result = await self.session.execute(
            select(Folder.id).where(
                Folder.name == name,
                Folder.owner_id == owner_id,
                Folder.parent_id == parent_id,
                Folder.is_deleted == False,  # noqa: E712
            )
        )
        return result.scalar_one_or_none() is not None

    async def get_subtree_ids(self, root_id: uuid.UUID) -> list[uuid.UUID]:
        """Return all folder IDs in subtree using recursive CTE."""
        cte = (
            select(Folder.id)
            .where(Folder.id == root_id)
            .cte(name="folder_subtree", recursive=True)
        )
        cte = cte.union_all(
            select(Folder.id).where(Folder.parent_id == cte.c.id)
        )
        result = await self.session.execute(select(cte.c.id))
        return [row[0] for row in result.all()]

    async def get_folder_size(self, folder_id: uuid.UUID) -> dict:
        """Calculate recursive folder size using CTE."""
        cte = (
            select(Folder.id)
            .where(Folder.id == folder_id)
            .cte(name="subtree", recursive=True)
        )
        cte = cte.union_all(
            select(Folder.id).where(Folder.parent_id == cte.c.id)
        )
        subquery = select(cte.c.id).subquery()

        file_count_result = await self.session.execute(
            select(func.count(File.id), func.coalesce(func.sum(File.file_size_bytes), 0))
            .where(
                File.folder_id.in_(select(subquery.c.id)),
                File.is_deleted == False,  # noqa: E712
            )
        )
        fc, fs = file_count_result.one()

        folder_count_result = await self.session.execute(
            select(func.count(Folder.id))
            .where(
                Folder.id.in_(select(subquery.c.id)),
                Folder.is_deleted == False,  # noqa: E712
            )
        )
        total_folders = folder_count_result.scalar_one()

        return {
            "folder_id": folder_id,
            "file_count": fc,
            "folder_count": total_folders - 1 if total_folders > 0 else 0,
            "total_size_bytes": fs or 0,
        }

    async def get_breadcrumbs(self, folder_id: uuid.UUID, owner_id: uuid.UUID) -> list[Folder]:
        """Walk up the parent chain to root, owner-scoped at every level."""
        breadcrumbs: list[Folder] = []
        current = await self.get_by_id(folder_id, owner_id)
        if current is None:
            return breadcrumbs
        breadcrumbs.append(current)
        while current.parent_id is not None:
            current = await self.get_by_id(current.parent_id, owner_id)
            if current is None:
                break
            breadcrumbs.append(current)
        breadcrumbs.reverse()
        return breadcrumbs

    async def get_children(
        self, folder_id: uuid.UUID, owner_id: uuid.UUID
    ) -> list[Folder]:
        result = await self.session.execute(
            select(Folder).where(
                Folder.parent_id == folder_id,
                Folder.owner_id == owner_id,
                Folder.is_deleted == False,  # noqa: E712
            ).order_by(Folder.name.asc())
        )
        return list(result.scalars().all())

    async def move(self, folder: Folder, new_parent_id: uuid.UUID | None) -> Folder:
        folder.parent_id = new_parent_id
        self.session.add(folder)
        await self.session.flush()
        logger.info("folder_moved", folder_id=str(folder.id), new_parent_id=str(new_parent_id))
        return folder

    async def has_access(self, folder_id: uuid.UUID, user_id: uuid.UUID,
                          *, include_deleted: bool = False) -> bool:
        """Check if user has access to a folder (owner or permission), walking up parent chain."""
        folder = await self.get_by_id_any_owner(folder_id)
        if folder is None:
            return False
        if not include_deleted and folder.is_deleted:
            return False
        if folder.owner_id == user_id:
            return True
        from app.models.sharing import Permission
        perm_result = await self.session.execute(
            select(Permission).where(
                Permission.user_id == user_id,
                Permission.resource_type == "folder",
                Permission.resource_id == folder_id,
            )
        )
        if perm_result.scalar_one_or_none() is not None:
            return True
        if folder.parent_id:
            return await self.has_access(folder.parent_id, user_id, include_deleted=include_deleted)
        return False

    async def get_by_id_with_access(
        self, folder_id: uuid.UUID, user_id: uuid.UUID, *, include_deleted: bool = False
    ) -> Folder | None:
        if await self.has_access(folder_id, user_id, include_deleted=include_deleted):
            return await self.get_by_id_any_owner(folder_id)
        return None

    async def is_ancestor(self, ancestor_id: uuid.UUID, descendant_id: uuid.UUID) -> bool:
        """Check if ancestor is in the parent chain of descendant."""
        current = await self.get_by_id_any_owner(descendant_id)
        while current is not None:
            if current.id == ancestor_id:
                return True
            if current.parent_id is None:
                break
            current = await self.get_by_id_any_owner(current.parent_id)
        return False


class FileRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(
        self,
        *,
        owner_id: uuid.UUID,
        folder_id: uuid.UUID | None,
        original_filename: str,
        stored_blob_name: str,
        mime_type: str | None,
        extension: str | None,
        checksum_sha256: str,
        file_size_bytes: int,
    ) -> File:
        file_record = File(
            owner_id=owner_id,
            folder_id=folder_id,
            original_filename=original_filename,
            stored_blob_name=stored_blob_name,
            mime_type=mime_type,
            extension=extension,
            checksum_sha256=checksum_sha256,
            file_size_bytes=file_size_bytes,
        )
        self.session.add(file_record)
        await self.session.flush()
        logger.info(
            "file_created", file_id=str(file_record.id), name=original_filename, size=file_size_bytes
        )
        return file_record

    async def get_by_id(
        self, file_id: uuid.UUID, owner_id: uuid.UUID, *, include_deleted: bool = False
    ) -> File | None:
        conditions = [File.id == file_id, File.owner_id == owner_id]
        if not include_deleted:
            conditions.append(File.is_deleted == False)  # noqa: E712
        result = await self.session.execute(select(File).where(*conditions))
        return result.scalar_one_or_none()

    async def get_by_id_any(self, file_id: uuid.UUID) -> File | None:
        result = await self.session.execute(select(File).where(File.id == file_id))
        return result.scalar_one_or_none()

    async def find_by_name(
        self, owner_id: uuid.UUID, folder_id: uuid.UUID | None, filename: str,
    ) -> File | None:
        result = await self.session.execute(
            select(File).where(
                File.owner_id == owner_id,
                File.folder_id == folder_id,
                File.original_filename == filename,
                File.is_deleted == False,  # noqa: E712
            )
        )
        return result.scalar_one_or_none()

    async def get_by_id_with_access(
        self, file_id: uuid.UUID, user_id: uuid.UUID, *, include_deleted: bool = False
    ) -> File | None:
        """Get file if user is owner OR has explicit/inherited permission to read it."""

        result = await self.session.execute(
            select(File).where(File.id == file_id)
        )
        file_record = result.scalar_one_or_none()
        if file_record is None:
            return None
        if not include_deleted and file_record.is_deleted:
            return None
        if file_record.owner_id == user_id:
            return file_record
        from app.models.sharing import Permission
        direct = await self.session.execute(
            select(Permission).where(
                Permission.user_id == user_id,
                Permission.resource_type == "file",
                Permission.resource_id == file_id,
            )
        )
        if direct.scalar_one_or_none() is not None:
            return file_record
        if file_record.folder_id:
            from app.repositories.file import FolderRepository
            folder_repo = FolderRepository(self.session)
            if await folder_repo.has_access(file_record.folder_id, user_id):
                return file_record
        return None

    async def list_files(
        self,
        owner_id: uuid.UUID,
        folder_id: uuid.UUID | None = None,
        *,
        offset: int = 0,
        limit: int = 50,
    ) -> tuple[list[File], int]:
        base = select(File).where(
            File.owner_id == owner_id,
            File.folder_id == folder_id,
            File.is_deleted == False,  # noqa: E712
        )
        total_q = select(func.count(File.id)).where(
            File.owner_id == owner_id,
            File.folder_id == folder_id,
            File.is_deleted == False,  # noqa: E712
        )
        total = (await self.session.execute(total_q)).scalar_one()
        query = base.order_by(File.original_filename.asc()).offset(offset).limit(limit)
        result = await self.session.execute(query)
        return list(result.scalars().all()), total

    async def list_trash(
        self, owner_id: uuid.UUID, *, offset: int = 0, limit: int = 50
    ) -> tuple[list[File], int]:
        base = select(File).where(
            File.owner_id == owner_id, File.is_deleted == True  # noqa: E712
        )
        total_q = select(func.count()).select_from(File).where(
            File.owner_id == owner_id, File.is_deleted == True  # noqa: E712
        )
        total = (await self.session.execute(total_q)).scalar_one()
        query = base.order_by(File.deleted_at.desc().nullslast()).offset(offset).limit(limit)
        result = await self.session.execute(query)
        return list(result.scalars().all()), total

    async def soft_delete(self, file_record: File) -> None:
        file_record.soft_delete()
        self.session.add(file_record)
        await self.session.flush()
        logger.info("file_soft_deleted", file_id=str(file_record.id))

    async def restore(self, file_record: File) -> None:
        file_record.restore()
        self.session.add(file_record)
        await self.session.flush()
        logger.info("file_restored", file_id=str(file_record.id))

    async def permanent_delete(self, file_record: File) -> None:
        await self.session.delete(file_record)
        await self.session.flush()
        logger.info("file_permanently_deleted", file_id=str(file_record.id))

    async def move(self, file_record: File, new_folder_id: uuid.UUID | None) -> File:
        file_record.folder_id = new_folder_id
        self.session.add(file_record)
        await self.session.flush()
        logger.info("file_moved", file_id=str(file_record.id), new_folder_id=str(new_folder_id))
        return file_record

    async def get_files_in_folder(
        self, folder_id: uuid.UUID, *, include_deleted: bool = False
    ) -> list[File]:
        conditions = [File.folder_id == folder_id]
        if not include_deleted:
            conditions.append(File.is_deleted == False)  # noqa: E712
        result = await self.session.execute(select(File).where(*conditions))
        return list(result.scalars().all())

    async def get_files_in_folders(
        self, folder_ids: list[uuid.UUID], *, include_deleted: bool = False
    ) -> list[File]:
        conditions = [File.folder_id.in_(folder_ids)]
        if not include_deleted:
            conditions.append(File.is_deleted == False)  # noqa: E712
        result = await self.session.execute(select(File).where(*conditions))
        return list(result.scalars().all())
