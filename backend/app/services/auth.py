from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.jwt import blacklist_token, create_access_token, create_refresh_token, decode_token
from app.auth.password import hash_password, verify_password
from app.config.settings import settings
from app.core.exceptions import AuthenticationError, ConflictError, NotFoundError
from app.core.logging_config import get_logger
from app.repositories.user import RefreshTokenRepository, UserRepository
from app.schemas.auth import LoginRequest, RegisterRequest, TokenResponse, UserResponse

logger = get_logger(__name__)


class AuthService:
    def __init__(self, session: AsyncSession) -> None:
        self.user_repo = UserRepository(session)
        self.token_repo = RefreshTokenRepository(session)

    async def register(self, request: RegisterRequest) -> UserResponse:
        existing = await self.user_repo.exists_by_email(request.email)
        if existing:
            raise ConflictError("A user with this email already exists")

        password_hash_value = hash_password(request.password)
        user = await self.user_repo.create(
            email=request.email,
            password_hash=password_hash_value,
            full_name=request.full_name,
        )

        logger.info(
            "user_registered",
            user_id=str(user.id),
            email=user.email,
        )
        return UserResponse.model_validate(user)

    async def login(self, request: LoginRequest) -> TokenResponse:
        user = await self.user_repo.get_by_email(request.email)
        if user is None:
            raise AuthenticationError("Invalid email or password")

        if not user.is_active:
            raise AuthenticationError("Account is deactivated")

        if not verify_password(request.password, user.password_hash):
            logger.warning(
                "login_failed_invalid_password",
                user_id=str(user.id),
                email=user.email,
            )
            raise AuthenticationError("Invalid email or password")

        return await self._generate_tokens(user.id, str(user.role.value))

    async def refresh_access_token(self, raw_refresh_token: str) -> TokenResponse:
        payload = decode_token(raw_refresh_token)

        if payload.get("type") != "refresh":
            raise AuthenticationError("Invalid token type")

        token_record = await self.token_repo.get_by_token(raw_refresh_token)
        if token_record is None:
            raise AuthenticationError("Refresh token not recognized")

        if not token_record.is_valid():
            raise AuthenticationError("Refresh token expired or revoked")

        user_id = uuid.UUID(payload["sub"])
        user = await self.user_repo.get_by_id(user_id)
        if user is None:
            raise AuthenticationError("User not found")

        if not user.is_active:
            raise AuthenticationError("Account is deactivated")

        await self.token_repo.revoke(token_record)
        return await self._generate_tokens(user.id, str(user.role.value))

    async def logout(self, raw_refresh_token: str, raw_access_token: str = "") -> None:
        token_record = await self.token_repo.get_by_token(raw_refresh_token)
        if token_record is not None:
            await self.token_repo.revoke(token_record)
            logger.info("user_logged_out", user_id=token_record.user_id)
        if raw_access_token:
            try:
                payload = decode_token(raw_access_token)
                jti = payload.get("jti")
                exp = payload.get("exp")
                if jti and exp:
                    from datetime import UTC, datetime
                    expires_at = datetime.fromtimestamp(exp, tz=UTC)
                    await blacklist_token(jti, expires_at)
            except Exception:
                pass

    async def get_current_user(self, access_token: str) -> UserResponse:
        payload = decode_token(access_token)

        if payload.get("type") != "access":
            raise AuthenticationError("Invalid token type")

        user_id = uuid.UUID(payload["sub"])
        user = await self.user_repo.get_by_id(user_id)
        if user is None:
            raise NotFoundError("User", str(user_id))

        if not user.is_active:
            raise AuthenticationError("Account is deactivated")

        return UserResponse.model_validate(user)

    async def _generate_tokens(
        self, user_id: uuid.UUID, role: str
    ) -> TokenResponse:
        access_token = create_access_token(user_id, role)

        expires_at = datetime.now(UTC) + timedelta(
            days=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS
        )
        refresh_token = create_refresh_token(user_id)
        await self.token_repo.create(user_id, refresh_token, expires_at)

        logger.info("tokens_generated", user_id=str(user_id))
        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
        )
