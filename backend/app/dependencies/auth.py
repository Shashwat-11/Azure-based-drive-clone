from __future__ import annotations

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.jwt import decode_token, is_token_blacklisted
from app.core.exceptions import AuthenticationError, AuthorizationError
from app.core.logging_config import get_logger
from app.dependencies.database import get_db
from app.models.user import UserRole
from app.schemas.auth import UserResponse

logger = get_logger(__name__)

security_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security_scheme),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
    request: Request = None,  # noqa: B008
) -> UserResponse:
    logger.debug(
        "get_current_user_enter",
        has_credentials=credentials is not None,
    )

    if credentials is None:
        logger.debug("get_current_user_no_credentials")
        raise AuthenticationError("Authentication required")

    if credentials.scheme.lower() != "bearer":
        logger.debug("get_current_user_wrong_scheme", scheme=credentials.scheme)
        raise AuthenticationError("Invalid authentication scheme")

    raw_token = credentials.credentials
    if raw_token.lower().startswith("bearer "):
        logger.debug("get_current_user_stripping_bearer_prefix")
        raw_token = raw_token[7:]

    logger.debug("get_current_user_decoding_token")
    payload = decode_token(raw_token)
    logger.debug("get_current_user_token_decoded", sub=payload.get("sub"))

    jti = payload.get("jti")
    if jti:
        logger.debug("get_current_user_checking_blacklist", jti=jti[:8] + "...")
        is_blacklisted = await is_token_blacklisted(jti)
        logger.debug("get_current_user_blacklist_checked", jti=jti[:8] + "...", blacklisted=is_blacklisted)
        if is_blacklisted:
            logger.debug("get_current_user_blacklisted", jti=jti)
            raise AuthenticationError("Token has been revoked")

    from app.services.auth import AuthService

    logger.debug("get_current_user_looking_up_user")
    auth_service = AuthService(db)
    try:
        user = await auth_service.get_current_user(raw_token)
        logger.debug("get_current_user_success", user_id=str(user.id), role=user.role)
        return user
    except AuthenticationError:
        raise
    except Exception as exc:
        logger.warning("get_current_user_service_error", error=str(exc))
        raise AuthenticationError("Authentication failed") from exc


def require_role(*allowed_roles: UserRole):
    async def role_checker(
        current_user: UserResponse = Depends(get_current_user),  # noqa: B008
    ) -> UserResponse:
        user_role = UserRole(current_user.role)
        if user_role not in allowed_roles:
            raise AuthorizationError(
                f"Role '{user_role.value}' does not have permission for this action"
            )
        return current_user

    return role_checker
