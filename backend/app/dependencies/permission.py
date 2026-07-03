from __future__ import annotations

import uuid

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AuthorizationError, NotFoundError
from app.dependencies.auth import get_current_user
from app.dependencies.database import get_db
from app.repositories.file import FileRepository, FolderRepository
from app.repositories.sharing import PermissionRepository
from app.schemas.auth import UserResponse

_ROLE_HIERARCHY = {
    "owner": 4,
    "editor": 3,
    "viewer": 2,
    "commenter": 1,
}

_MIN_ROLE_FOR_OPERATION = {
    "read": 2,      # viewer+
    "write": 3,     # editor+
    "manage": 4,    # owner only
}


def _has_role(current_role: str, required: str) -> bool:
    return _ROLE_HIERARCHY.get(current_role, 0) >= _ROLE_HIERARCHY.get(required, 0)


async def _get_effective_role(
    db: AsyncSession, user_id: uuid.UUID, resource_type: str, resource_id: uuid.UUID
) -> str | None:
    """Determine effective role for a user on a resource, checking ownership and inheritance."""
    if resource_type == "file":
        file_repo = FileRepository(db)
        file_record = await file_repo.get_by_id(resource_id, user_id)
        if file_record is not None:
            return "owner"
        file_record = await file_repo.get_by_id_any(resource_id)
        if file_record is None:
            return None
        perm_repo = PermissionRepository(db)
        direct = await perm_repo.get_by_user_and_resource(user_id, "file", resource_id)
        if direct is not None:
            return direct.role
        if file_record.folder_id:
            return await _get_effective_role(db, user_id, "folder", file_record.folder_id)
        return None

    if resource_type == "folder":
        folder_repo = FolderRepository(db)
        folder = await folder_repo.get_by_id(resource_id, user_id)
        if folder is not None:
            return "owner"
        folder = await folder_repo.get_by_id_any_owner(resource_id)
        if folder is None:
            return None
        perm_repo = PermissionRepository(db)
        direct = await perm_repo.get_by_user_and_resource(user_id, "folder", resource_id)
        if direct is not None:
            return direct.role
        if folder.parent_id:
            return await _get_effective_role(db, user_id, "folder", folder.parent_id)
        return None

    return None


async def get_effective_permission(
    db: AsyncSession, user_id: uuid.UUID, resource_type: str, resource_id: uuid.UUID
) -> str | None:
    return await _get_effective_role(db, user_id, resource_type, resource_id)


def require_file_access(operation: str = "read"):
    """Dependency factory: require minimum role for file access."""
    async def checker(
        file_id: str,
        current_user: UserResponse = Depends(get_current_user),  # noqa: B008
        db: AsyncSession = Depends(get_db),  # noqa: B008
    ) -> UserResponse:
        effective = await _get_effective_role(db, current_user.id, "file", uuid.UUID(file_id))
        if effective is None:
            raise NotFoundError("File", file_id)
        required = _MIN_ROLE_FOR_OPERATION.get(operation, "viewer")
        if not _has_role(effective, required):
            raise AuthorizationError("Insufficient permissions for this operation")
        return current_user
    return checker


def require_folder_access(operation: str = "read"):
    """Dependency factory: require minimum role for folder access."""
    async def checker(
        folder_id: str,
        current_user: UserResponse = Depends(get_current_user),  # noqa: B008
        db: AsyncSession = Depends(get_db),  # noqa: B008
    ) -> UserResponse:
        effective = await _get_effective_role(db, current_user.id, "folder", uuid.UUID(folder_id))
        if effective is None:
            raise NotFoundError("Folder", folder_id)
        required = _MIN_ROLE_FOR_OPERATION.get(operation, "viewer")
        if not _has_role(effective, required):
            raise AuthorizationError("Insufficient permissions for this operation")
        return current_user
    return checker
