from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies.auth import get_current_user, require_role, security_scheme
from app.dependencies.database import get_db
from app.core.logging_config import get_logger
from app.models.user import UserRole

logger = get_logger(__name__)
from app.schemas.auth import (
    LoginRequest,
    LogoutRequest,
    MessageResponse,
    RefreshRequest,
    RegisterRequest,
    TokenResponse,
    UserResponse,
)
from app.services.auth import AuthService

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/register", response_model=UserResponse, status_code=201)
async def register(
    request: RegisterRequest,
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> UserResponse:
    logger.debug("register_handler_enter", email=request.email)
    service = AuthService(db)
    logger.debug("register_handler_calling_service")
    return await service.register(request)


@router.post("/login", response_model=TokenResponse)
async def login(
    request: LoginRequest,
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> TokenResponse:
    service = AuthService(db)
    return await service.login(request)


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    request: RefreshRequest,
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> TokenResponse:
    service = AuthService(db)
    return await service.refresh_access_token(request.refresh_token)


@router.post("/logout", response_model=MessageResponse)
async def logout(
    request_data: LogoutRequest,
    db: AsyncSession = Depends(get_db),  # noqa: B008
    credentials: HTTPAuthorizationCredentials | None = Depends(security_scheme),  # noqa: B008
) -> MessageResponse:
    service = AuthService(db)
    raw_token = credentials.credentials if credentials else ""
    if raw_token.lower().startswith("bearer "):
        raw_token = raw_token[7:]
    await service.logout(request_data.refresh_token, raw_token)
    return MessageResponse(success=True, message="Logged out successfully", code="LOGGED_OUT")


@router.get("/me", response_model=UserResponse)
async def get_me(
    current_user: UserResponse = Depends(get_current_user),  # noqa: B008
) -> UserResponse:
    return current_user


@router.get("/admin-only", response_model=MessageResponse)
async def admin_only(
    _: UserResponse = Depends(require_role(UserRole.ADMIN)),  # noqa: B008
) -> MessageResponse:
    return MessageResponse(
        success=True,
        message="Welcome, admin",
        code="ADMIN_ACCESS",
    )
