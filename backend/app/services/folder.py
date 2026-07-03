from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AuthorizationError, ConflictError, NotFoundError, ValidationError
from app.core.logging_config import get_logger
from app.models.file import Folder
from app.repositories.file import FileRepository, FolderRepository
from app.schemas.file import FolderCreateRequest, FolderResponse, FolderUpdateRequest
from app.services.audit import AuditService

logger = get_logger(__name__)


class FolderService:
    def __init__(self, session: AsyncSession, storage_service: Any = None) -> None:
        self.repo = FolderRepository(session)
        self.file_repo = FileRepository(session)
        self.audit = AuditService()
        self.session = session
        self._storage_service = storage_service

    async def _get_folder_or_raise(self, folder_id: uuid.UUID, user_id: uuid.UUID,
                                    *, include_deleted: bool = False) -> Folder:
        folder = await self.repo.get_by_id_with_access(folder_id, user_id, include_deleted=include_deleted)
        if folder is None:
            raise NotFoundError("Folder", str(folder_id))
        return folder

    async def _get_folder_with_role(self, folder_id: uuid.UUID, user_id: uuid.UUID,
                                     min_role: str, *, include_deleted: bool = False) -> Folder:
        from app.dependencies.permission import _ROLE_HIERARCHY, _get_effective_role

        folder = await self._get_folder_or_raise(folder_id, user_id, include_deleted=include_deleted)
        effective = await _get_effective_role(self.session, user_id, "folder", folder_id)
        if effective is None or _ROLE_HIERARCHY.get(effective, 0) < _ROLE_HIERARCHY.get(min_role, 0):
            raise AuthorizationError("Insufficient permissions for this operation")
        return folder

    async def create(self, owner_id: uuid.UUID, request: FolderCreateRequest, *, trace_id: str = ""
                     ) -> FolderResponse:
        if await self.repo.exists_by_name(request.name, owner_id, request.parent_id):
            raise ConflictError("A folder with this name already exists in this location")
        if request.parent_id is not None:
            parent = await self.repo.get_by_id(request.parent_id, owner_id)
            if parent is None:
                raise NotFoundError("Parent folder", str(request.parent_id))
        folder = await self.repo.create(name=request.name, owner_id=owner_id, parent_id=request.parent_id)
        self.audit.log_folder_created(trace_id=trace_id, user_id=str(owner_id), folder_id=str(folder.id),
                                      name=folder.name, parent_id=str(request.parent_id) if request.parent_id else None)
        return FolderResponse.model_validate(folder)

    async def get(self, folder_id: uuid.UUID, user_id: uuid.UUID) -> FolderResponse:
        return FolderResponse.model_validate(await self._get_folder_or_raise(folder_id, user_id))

    async def list_folders(self, owner_id: uuid.UUID, parent_id: uuid.UUID | None = None,
                           *, offset: int = 0, limit: int = 50) -> tuple[list[FolderResponse], int]:
        folders, total = await self.repo.list_folders(owner_id, parent_id=parent_id, offset=offset, limit=limit)
        return [FolderResponse.model_validate(f) for f in folders], total

    async def update(self, folder_id: uuid.UUID, user_id: uuid.UUID, request: FolderUpdateRequest
                     ) -> FolderResponse:
        folder = await self._get_folder_with_role(folder_id, user_id, "editor")
        if request.name is not None:
            if await self.repo.exists_by_name(request.name, user_id, folder.parent_id):
                raise ConflictError("A folder with this name already exists")
            folder.name = request.name
        updated = await self.repo.update(folder)
        return FolderResponse.model_validate(updated)

    async def delete(self, folder_id: uuid.UUID, user_id: uuid.UUID, *, trace_id: str = "") -> None:
        folder = await self._get_folder_with_role(folder_id, user_id, "editor")
        subtree_ids = await self.repo.get_subtree_ids(folder_id)
        files = await self.file_repo.get_files_in_folders(subtree_ids)
        for f in files:
            await self.file_repo.soft_delete(f)
        for fid in subtree_ids:
            fld = await self.repo.get_by_id_any_owner(fid)
            if fld is not None:
                await self.repo.soft_delete(fld)
        self.audit.log_folder_deleted(trace_id=trace_id, user_id=str(user_id), folder_id=str(folder_id),
                                      name=folder.name)

    async def move(self, folder_id: uuid.UUID, user_id: uuid.UUID, new_parent_id: uuid.UUID | None,
                   *, trace_id: str = "") -> FolderResponse:
        folder = await self._get_folder_with_role(folder_id, user_id, "editor")
        if new_parent_id is not None:
            target = await self.repo.get_by_id(new_parent_id, user_id)
            if target is None:
                raise NotFoundError("Target folder", str(new_parent_id))
        if new_parent_id == folder_id:
            raise ValidationError("Cannot move a folder into itself")
        if new_parent_id is not None and await self.repo.is_ancestor(folder_id, new_parent_id):
            raise ValidationError("Cannot move a folder into one of its descendants")
        if await self.repo.exists_by_name(folder.name, user_id, new_parent_id):
            raise ConflictError("A folder with this name already exists in the target location")
        updated = await self.repo.move(folder, new_parent_id)
        return FolderResponse.model_validate(updated)

    async def copy(self, folder_id: uuid.UUID, user_id: uuid.UUID, target_parent_id: uuid.UUID | None,
                   *, trace_id: str = "") -> FolderResponse:
        folder = await self._get_folder_with_role(folder_id, user_id, "editor")
        if target_parent_id is not None:
            target = await self.repo.get_by_id(target_parent_id, user_id)
            if target is None:
                raise NotFoundError("Target folder", str(target_parent_id))
        new_folder = await self._copy_subtree(folder, user_id, target_parent_id)
        return FolderResponse.model_validate(new_folder)

    async def _copy_subtree(self, source: Folder, owner_id: uuid.UUID, new_parent_id: uuid.UUID | None
                            ) -> Folder:
        copy_name = source.name
        counter = 1
        while await self.repo.exists_by_name(copy_name, owner_id, new_parent_id):
            copy_name = f"{source.name} (Copy {counter})"
            counter += 1
        new_folder = await self.repo.create(name=copy_name, owner_id=owner_id, parent_id=new_parent_id)
        children = await self.repo.get_children(source.id, owner_id)
        for child in children:
            await self._copy_subtree(child, owner_id, new_folder.id)
        files = await self.file_repo.get_files_in_folder(source.id)
        for f in files:
            new_blob_name = f"{owner_id}/{uuid.uuid4()}"
            from app.services.storage import StorageService
            storage = self._storage_service or StorageService()
            backend = await storage._get_backend()
            await backend.copy(f.stored_blob_name, new_blob_name)
            await self.file_repo.create(
                owner_id=owner_id, folder_id=new_folder.id,
                original_filename=f.original_filename, stored_blob_name=new_blob_name,
                mime_type=f.mime_type, extension=f.extension,
                checksum_sha256=f.checksum_sha256 or "", file_size_bytes=f.file_size_bytes)
        return new_folder

    async def restore(self, folder_id: uuid.UUID, user_id: uuid.UUID, *, trace_id: str = ""
                      ) -> FolderResponse:
        folder = await self.repo.get_by_id_with_access(folder_id, user_id, include_deleted=True)
        if folder is None:
            raise NotFoundError("Folder", str(folder_id))
        if not folder.is_deleted:
            raise ValidationError("Folder is not in trash")
        if folder.parent_id is not None:
            parent = await self.repo.get_by_id(folder.parent_id, user_id)
            if parent is None:
                raise ValidationError("Parent folder no longer exists — cannot restore")
        if await self.repo.exists_by_name(folder.name, user_id, folder.parent_id):
            folder.name = f"{folder.name} (Restored)"
        subtree_ids = await self.repo.get_subtree_ids(folder_id)
        for fid in subtree_ids:
            fld = await self.repo.get_by_id_any_owner(fid)
            if fld is not None and fld.is_deleted:
                await self.repo.restore(fld)
        files = await self.file_repo.get_files_in_folders(subtree_ids, include_deleted=True)
        for f in files:
            if f.is_deleted:
                await self.file_repo.restore(f)
        return FolderResponse.model_validate(folder)

    async def permanent_delete(self, folder_id: uuid.UUID, user_id: uuid.UUID, *, trace_id: str = ""
                               ) -> None:
        folder = await self.repo.get_by_id_with_access(folder_id, user_id, include_deleted=True)
        if folder is None:
            raise NotFoundError("Folder", str(folder_id))
        subtree_ids = await self.repo.get_subtree_ids(folder_id)
        files = await self.file_repo.get_files_in_folders(subtree_ids, include_deleted=True)
        blob_names = [f.stored_blob_name for f in files]
        for f in files:
            await self.file_repo.permanent_delete(f)
        for fid in subtree_ids:
            fld = await self.repo.get_by_id_any_owner(fid)
            if fld is not None:
                await self.repo.permanent_delete(fld)
        if blob_names:
            try:
                from app.services.storage import StorageService
                storage = self._storage_service or StorageService()
                await storage.delete_blobs(blob_names)
            except Exception as exc:
                logger.error("permanent_delete_blob_cleanup_failed", count=len(blob_names), error=str(exc))

    async def get_tree(self, owner_id: uuid.UUID, root_id: uuid.UUID | None = None) -> list[dict]:
        if root_id is not None:
            folders = await self.repo.get_children(root_id, owner_id)
        else:
            folders, _ = await self.repo.list_folders(owner_id, parent_id=None)
        return [FolderResponse.model_validate(f).model_dump() for f in folders]

    async def get_breadcrumbs(self, folder_id: uuid.UUID, owner_id: uuid.UUID) -> list[FolderResponse]:
        crumbs = await self.repo.get_breadcrumbs(folder_id, owner_id)
        if not crumbs:
            raise NotFoundError("Folder", str(folder_id))
        return [FolderResponse.model_validate(c) for c in crumbs]

    async def get_folder_size(self, folder_id: uuid.UUID, owner_id: uuid.UUID) -> dict:
        folder = await self.repo.get_by_id(folder_id, owner_id)
        if folder is None:
            raise NotFoundError("Folder", str(folder_id))
        return await self.repo.get_folder_size(folder_id)

    async def list_trash(self, owner_id: uuid.UUID, *, offset: int = 0, limit: int = 50
                         ) -> tuple[list[FolderResponse], int]:
        folders, total = await self.repo.list_trash(owner_id, offset=offset, limit=limit)
        return [FolderResponse.model_validate(f) for f in folders], total

    async def empty_trash(self, owner_id: uuid.UUID, *, trace_id: str = "") -> int:
        from app.services.storage import StorageService
        storage = self._storage_service or StorageService()
        batch_size = 200
        total_count = 0
        while True:
            folders, _ = await self.repo.list_trash(owner_id, offset=0, limit=batch_size)
            files, _ = await self.file_repo.list_trash(owner_id, offset=0, limit=batch_size)
            if not folders and not files:
                break
            for f in files:
                try:
                    await storage.delete_blob(f.stored_blob_name)
                except Exception as exc:
                    logger.error("empty_trash_blob_cleanup_failed", file_id=str(f.id),
                                 blob_name=f.stored_blob_name, error=str(exc))
                await self.file_repo.permanent_delete(f)
                total_count += 1
            for fld in folders:
                subtree_ids = await self.repo.get_subtree_ids(fld.id)
                nested_files = await self.file_repo.get_files_in_folders(subtree_ids, include_deleted=True)
                for nf in nested_files:
                    try:
                        await storage.delete_blob(nf.stored_blob_name)
                    except Exception as exc:
                        logger.error("empty_trash_blob_cleanup_failed", file_id=str(nf.id),
                                     blob_name=nf.stored_blob_name, error=str(exc))
                    await self.file_repo.permanent_delete(nf)
                    total_count += 1
                for fid in subtree_ids:
                    to_delete = await self.repo.get_by_id_any_owner(fid)
                    if to_delete is not None:
                        await self.repo.permanent_delete(to_delete)
                total_count += 1
        return total_count

    async def rename(self, folder_id: uuid.UUID, user_id: uuid.UUID, new_name: str) -> FolderResponse:
        folder = await self._get_folder_with_role(folder_id, user_id, "editor")
        if await self.repo.exists_by_name(new_name, user_id, folder.parent_id):
            raise ConflictError("A folder with this name already exists")
        folder.name = new_name
        updated = await self.repo.update(folder)
        return FolderResponse.model_validate(updated)
