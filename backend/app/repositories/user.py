from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging_config import get_logger
from app.models.user import RefreshToken, User, UserRole

logger = get_logger(__name__)


class UserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(self, user_id: uuid.UUID) -> User | None:
        result = await self.session.execute(
            select(User).where(User.id == user_id, User.is_deleted == False)  # noqa: E712
        )
        return result.scalar_one_or_none()

    async def get_by_email(self, email: str) -> User | None:
        result = await self.session.execute(
            select(User).where(
                User.email == email.lower().strip(),
                User.is_deleted == False,  # noqa: E712
            )
        )
        return result.scalar_one_or_none()

    async def create(
        self, email: str, password_hash: str, full_name: str, *, role: UserRole = UserRole.USER
    ) -> User:
        role_value = role.value if isinstance(role, UserRole) else role
        user = User(
            email=email.lower().strip(),
            password_hash=password_hash,
            full_name=full_name,
            role=role_value,
        )
        self.session.add(user)
        await self.session.flush()
        logger.info("user_created", user_id=str(user.id), email=user.email)
        return user

    async def update(self, user: User) -> User:
        self.session.add(user)
        await self.session.flush()
        logger.debug("user_updated", user_id=str(user.id))
        return user

    async def exists_by_email(self, email: str) -> bool:
        result = await self.session.execute(
            select(User.id).where(
                User.email == email.lower().strip(),
                User.is_deleted == False,  # noqa: E712
            )
        )
        return result.scalar_one_or_none() is not None


class RefreshTokenRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, user_id: uuid.UUID, token: str, expires_at: datetime) -> RefreshToken:
        from app.auth.jwt import hash_token

        rt = RefreshToken(
            user_id=user_id,
            token_hash=hash_token(token),
            expires_at=expires_at,
        )
        self.session.add(rt)
        await self.session.flush()
        logger.debug("refresh_token_created", user_id=str(user_id), token_id=str(rt.id))
        return rt

    async def get_by_token(self, raw_token: str) -> RefreshToken | None:
        from app.auth.jwt import hash_token

        hashed = hash_token(raw_token)
        result = await self.session.execute(
            select(RefreshToken).where(RefreshToken.token_hash == hashed)
        )
        return result.scalar_one_or_none()

    async def revoke(self, token: RefreshToken) -> None:
        token.revoke()
        self.session.add(token)
        await self.session.flush()
        logger.debug("refresh_token_revoked", token_id=str(token.id))

    async def revoke_all_for_user(self, user_id: uuid.UUID) -> None:
        result = await self.session.execute(
            select(RefreshToken).where(
                RefreshToken.user_id == user_id,
                RefreshToken.is_revoked == False,  # noqa: E712
            )
        )
        tokens = result.scalars().all()
        for token in tokens:
            token.revoke()
            self.session.add(token)
        if tokens:
            await self.session.flush()
            logger.info(
                "all_refresh_tokens_revoked",
                user_id=str(user_id),
                count=len(tokens),
            )
