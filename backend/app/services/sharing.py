from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, ValidationError
from app.core.logging_config import get_logger
from app.repositories.file import FileRepository, FolderRepository
from app.repositories.sharing import PermissionRepository, SharedLinkRepository
from app.schemas.sharing import LinkResponse, PermissionResponse, ResourcePermissionsResponse, ShareRequest

logger = get_logger(__name__)


class PermissionService:
    def __init__(self, session: AsyncSession) -> None:
        self.repo = PermissionRepository(session)
        self.file_repo = FileRepository(session)
        self.folder_repo = FolderRepository(session)
        self.session = session

    async def _get_owner(self, resource_type: str, resource_id: uuid.UUID) -> uuid.UUID:
        if resource_type == "file":
            record = await self.file_repo.get_by_id_any(resource_id)
        else:
            record = await self.folder_repo.get_by_id_any_owner(resource_id)
        if record is None:
            raise NotFoundError(resource_type.capitalize(), str(resource_id))
        return record.owner_id

    async def share(self, resource_type: str, resource_id: uuid.UUID, owner_id: uuid.UUID,
                    request: ShareRequest, *, trace_id: str = "") -> PermissionResponse:
        if request.user_id == owner_id:
            raise ValidationError("Cannot share with the resource owner")
        owner = await self._get_owner(resource_type, resource_id)
        if owner != owner_id:
            raise ValidationError("Only the resource owner can manage permissions")
        perm = await self.repo.upsert(user_id=request.user_id, resource_type=resource_type,
                                      resource_id=resource_id, role=request.role, granted_by=owner_id)
        return PermissionResponse.model_validate(perm)

    async def remove_permission(self, perm_id: uuid.UUID, owner_id: uuid.UUID) -> None:
        perm = await self.repo.get_by_id(perm_id)
        if perm is None:
            raise NotFoundError("Permission", str(perm_id))
        owner = await self._get_owner(perm.resource_type, perm.resource_id)
        if owner != owner_id:
            raise ValidationError("Only the resource owner can manage permissions")
        await self.repo.delete(perm)

    async def update_permission(self, perm_id: uuid.UUID, owner_id: uuid.UUID, role: str
                                ) -> PermissionResponse:
        perm = await self.repo.get_by_id(perm_id)
        if perm is None:
            raise NotFoundError("Permission", str(perm_id))
        owner = await self._get_owner(perm.resource_type, perm.resource_id)
        if owner != owner_id:
            raise ValidationError("Only the resource owner can manage permissions")
        perm.role = role
        self.session.add(perm)
        await self.session.flush()
        return PermissionResponse.model_validate(perm)

    async def get_resource_permissions(self, resource_type: str, resource_id: uuid.UUID, owner_id: uuid.UUID
                                       ) -> ResourcePermissionsResponse:
        owner = await self._get_owner(resource_type, resource_id)
        if owner != owner_id:
            raise ValidationError("Only the resource owner can view permissions")
        perms = await self.repo.get_for_resource(resource_type, resource_id)
        return ResourcePermissionsResponse(
            owner_id=owner_id, permissions=[PermissionResponse.model_validate(p) for p in perms])

    async def get_shared_with_me(self, user_id: uuid.UUID, *, offset: int = 0, limit: int = 50
                                 ) -> tuple[list[dict], int]:
        perms, total = await self.repo.get_shared_with_me(user_id, offset=offset, limit=limit)
        items = [{"permission_id": str(p.id), "resource_type": p.resource_type,
                  "resource_id": str(p.resource_id), "role": p.role,
                  "granted_by": str(p.granted_by) if p.granted_by else None,
                  "created_at": str(p.created_at)} for p in perms]
        return items, total

    async def get_shared_by_me(self, user_id: uuid.UUID, *, offset: int = 0, limit: int = 50
                               ) -> tuple[list[dict], int]:
        perms, total = await self.repo.get_shared_by_me(user_id, offset=offset, limit=limit)
        items = [{"permission_id": str(p.id), "user_id": str(p.user_id),
                  "resource_type": p.resource_type, "resource_id": str(p.resource_id),
                  "role": p.role, "created_at": str(p.created_at)} for p in perms]
        return items, total

    async def transfer_ownership(self, resource_type: str, resource_id: uuid.UUID, owner_id: uuid.UUID,
                                 new_owner_id: uuid.UUID, *, trace_id: str = "") -> None:
        if new_owner_id == owner_id:
            raise ValidationError("New owner must be different from current owner")
        if resource_type == "file":
            record = await self.file_repo.get_by_id(resource_id, owner_id)
            if record is None:
                raise NotFoundError("File", str(resource_id))
            record.owner_id = new_owner_id
            self.session.add(record)
        else:
            record = await self.folder_repo.get_by_id(resource_id, owner_id)
            if record is None:
                raise NotFoundError("Folder", str(resource_id))
            record.owner_id = new_owner_id
            self.session.add(record)
        await self.session.flush()


class LinkService:
    def __init__(self, session: AsyncSession) -> None:
        self.repo = SharedLinkRepository(session)
        self.file_repo = FileRepository(session)
        self.folder_repo = FolderRepository(session)
        self.session = session

    async def _get_owner(self, resource_type: str, resource_id: uuid.UUID) -> uuid.UUID:
        if resource_type == "file":
            record = await self.file_repo.get_by_id_any(resource_id)
        else:
            record = await self.folder_repo.get_by_id_any_owner(resource_id)
        if record is None:
            raise NotFoundError(resource_type.capitalize(), str(resource_id))
        return record.owner_id

    async def create_link(self, user_id: uuid.UUID, resource_type: str, resource_id: uuid.UUID, *,
                          is_public: bool = True, password: str | None = None,
                          expires_at=None, max_downloads: int | None = None) -> LinkResponse:
        owner = await self._get_owner(resource_type, resource_id)
        if owner != user_id:
            raise ValidationError("Only the resource owner can create shared links")
        link = await self.repo.create(resource_type=resource_type, resource_id=resource_id,
                                      created_by=user_id, is_public=is_public, password=password,
                                      expires_at=expires_at, max_downloads=max_downloads)
        return LinkResponse.model_validate(link)

    async def get_link(self, token: str, password: str | None = None,
                       authenticated_user_id: uuid.UUID | None = None) -> LinkResponse:
        from app.auth.password import verify_password
        from app.core.exceptions import AuthenticationError

        link = await self.repo.get_by_token(token)
        if link is None:
            raise NotFoundError("Link", token)
        if not link.is_valid():
            raise ValidationError("Link is expired, disabled, or exhausted")
        if not link.is_public and authenticated_user_id is None:
            raise AuthenticationError("Authentication required for private links")
        if link.password_hash and (password is None or not verify_password(password, link.password_hash)):
            raise ValidationError("Invalid or missing link password")
        await self.repo.increment_downloads(link)
        return LinkResponse.model_validate(link)

    async def update_link(self, link_id: uuid.UUID, user_id: uuid.UUID, *,
                          is_public: bool | None = None,
                          password: str | None = None,
                          expires_at=None,
                          max_downloads: int | None = None,
                          is_enabled: bool | None = None) -> LinkResponse:
        from app.auth.password import hash_password

        link = await self.repo.get_by_id(link_id)
        if link is None or link.created_by != user_id:
            raise NotFoundError("Link", str(link_id))
        if is_public is not None:
            link.is_public = is_public
        if password is not None:
            link.password_hash = hash_password(password)
        if expires_at is not None:
            link.expires_at = expires_at
        if max_downloads is not None:
            link.max_downloads = max_downloads
        if is_enabled is not None:
            link.is_enabled = is_enabled
        await self.repo.update(link)
        return LinkResponse.model_validate(link)

    async def delete_link(self, link_id: uuid.UUID, user_id: uuid.UUID) -> None:
        link = await self.repo.get_by_id(link_id)
        if link is None or link.created_by != user_id:
            raise NotFoundError("Link", str(link_id))
        await self.repo.delete(link)

    async def list_links(self, user_id: uuid.UUID, *, offset: int = 0, limit: int = 50
                         ) -> tuple[list[LinkResponse], int]:
        links, total = await self.repo.list_by_creator(user_id, offset=offset, limit=limit)
        return [LinkResponse.model_validate(link) for link in links], total
