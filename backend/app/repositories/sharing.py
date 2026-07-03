from __future__ import annotations

import secrets
import uuid
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.password import hash_password
from app.core.logging_config import get_logger
from app.models.sharing import Permission, SharedLink

logger = get_logger(__name__)


class PermissionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def upsert(
        self, user_id: uuid.UUID, resource_type: str, resource_id: uuid.UUID, role: str, *, granted_by: uuid.UUID
    ) -> Permission:
        existing = await self.session.execute(
            select(Permission).where(
                Permission.user_id == user_id,
                Permission.resource_type == resource_type,
                Permission.resource_id == resource_id,
            )
        )
        perm = existing.scalar_one_or_none()
        if perm is not None:
            perm.role = role
            perm.granted_by = granted_by
        else:
            perm = Permission(
                user_id=user_id, resource_type=resource_type, resource_id=resource_id,
                role=role, granted_by=granted_by,
            )
        self.session.add(perm)
        await self.session.flush()
        logger.info("permission_upserted", user_id=str(user_id), resource_id=str(resource_id), role=role)
        return perm

    async def delete(self, perm: Permission) -> None:
        await self.session.delete(perm)
        await self.session.flush()
        logger.info("permission_deleted", perm_id=str(perm.id))

    async def get_by_id(self, perm_id: uuid.UUID) -> Permission | None:
        result = await self.session.execute(select(Permission).where(Permission.id == perm_id))
        return result.scalar_one_or_none()

    async def get_by_user_and_resource(
        self, user_id: uuid.UUID, resource_type: str, resource_id: uuid.UUID
    ) -> Permission | None:
        result = await self.session.execute(
            select(Permission).where(
                Permission.user_id == user_id,
                Permission.resource_type == resource_type,
                Permission.resource_id == resource_id,
            )
        )
        return result.scalar_one_or_none()

    async def get_for_resource(self, resource_type: str, resource_id: uuid.UUID) -> list[Permission]:
        result = await self.session.execute(
            select(Permission).where(
                Permission.resource_type == resource_type,
                Permission.resource_id == resource_id,
            )
        )
        return list(result.scalars().all())

    async def get_shared_with_me(
        self, user_id: uuid.UUID, *, offset: int = 0, limit: int = 50
    ) -> tuple[list[Permission], int]:
        base = select(Permission).where(Permission.user_id == user_id)
        total = (await self.session.execute(select(func.count()).select_from(base.subquery()))).scalar_one()
        query = base.order_by(Permission.created_at.desc()).offset(offset).limit(limit)
        result = await self.session.execute(query)
        return list(result.scalars().all()), total

    async def get_shared_by_me(
        self, user_id: uuid.UUID, *, offset: int = 0, limit: int = 50
    ) -> tuple[list[Permission], int]:
        base = select(Permission).where(Permission.granted_by == user_id)
        total = (await self.session.execute(select(func.count()).select_from(base.subquery()))).scalar_one()
        query = base.order_by(Permission.created_at.desc()).offset(offset).limit(limit)
        result = await self.session.execute(query)
        return list(result.scalars().all()), total


class SharedLinkRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(
        self, resource_type: str, resource_id: uuid.UUID, created_by: uuid.UUID, *,
        is_public: bool = True, password: str | None = None,
        expires_at: datetime | None = None, max_downloads: int | None = None,
    ) -> SharedLink:
        token = secrets.token_urlsafe(32)
        password_hash_value = hash_password(password) if password else None
        link = SharedLink(
            resource_type=resource_type, resource_id=resource_id,
            token=token, is_public=is_public, password_hash=password_hash_value,
            expires_at=expires_at, max_downloads=max_downloads, created_by=created_by,
        )
        self.session.add(link)
        await self.session.flush()
        logger.info("shared_link_created", link_id=str(link.id), token=token[:8])
        return link

    async def get_by_token(self, token: str) -> SharedLink | None:
        result = await self.session.execute(select(SharedLink).where(SharedLink.token == token))
        return result.scalar_one_or_none()

    async def get_by_id(self, link_id: uuid.UUID) -> SharedLink | None:
        result = await self.session.execute(select(SharedLink).where(SharedLink.id == link_id))
        return result.scalar_one_or_none()

    async def list_by_creator(
        self, user_id: uuid.UUID, *, offset: int = 0, limit: int = 50
    ) -> tuple[list[SharedLink], int]:
        base = select(SharedLink).where(SharedLink.created_by == user_id)
        total = (await self.session.execute(select(func.count()).select_from(base.subquery()))).scalar_one()
        query = base.order_by(SharedLink.created_at.desc()).offset(offset).limit(limit)
        result = await self.session.execute(query)
        return list(result.scalars().all()), total

    async def update(self, link: SharedLink) -> SharedLink:
        self.session.add(link)
        await self.session.flush()
        return link

    async def delete(self, link: SharedLink) -> None:
        await self.session.delete(link)
        await self.session.flush()
        logger.info("shared_link_deleted", link_id=str(link.id))

    async def increment_downloads(self, link: SharedLink) -> None:
        link.download_count += 1
        self.session.add(link)
        await self.session.flush()
