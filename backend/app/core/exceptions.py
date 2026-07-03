from __future__ import annotations

from typing import Any


class AppError(Exception):
    """Base application error with standardized response fields."""

    def __init__(
        self,
        message: str,
        *,
        code: str | None = None,
        status_code: int = 500,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.code = code or self._default_code()
        self.status_code = status_code
        self.details = details or {}

    @staticmethod
    def _default_code() -> str:
        return "INTERNAL_ERROR"


class ValidationError(AppError):
    def __init__(
        self,
        message: str,
        *,
        code: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message, code=code or "VALIDATION_ERROR", status_code=422, details=details)


class AuthenticationError(AppError):
    def __init__(self, message: str = "Authentication required") -> None:
        super().__init__(message, code="AUTHENTICATION_REQUIRED", status_code=401)


class AuthorizationError(AppError):
    def __init__(self, message: str = "Insufficient permissions") -> None:
        super().__init__(message, code="FORBIDDEN", status_code=403)


class NotFoundError(AppError):
    def __init__(self, resource: str = "Resource", identifier: str | None = None) -> None:
        message = f"{resource} not found"
        if identifier:
            message = f"{resource} with id '{identifier}' not found"
        super().__init__(message, code="NOT_FOUND", status_code=404)


class ConflictError(AppError):
    def __init__(self, message: str = "Resource already exists") -> None:
        super().__init__(message, code="CONFLICT", status_code=409)


class RateLimitError(AppError):
    def __init__(
        self,
        message: str = "Too many requests",
        *,
        retry_after: int | None = None,
    ) -> None:
        super().__init__(
            message,
            code="RATE_LIMIT_EXCEEDED",
            status_code=429,
            details={"retry_after": retry_after} if retry_after else {},
        )


class ServiceUnavailableError(AppError):
    def __init__(self, service: str = "Service") -> None:
        super().__init__(
            f"{service} is currently unavailable",
            code="SERVICE_UNAVAILABLE",
            status_code=503,
        )


class StorageError(AppError):
    def __init__(
        self,
        message: str = "Storage operation failed",
        *,
        code: str | None = None,
    ) -> None:
        super().__init__(message, code=code or "STORAGE_ERROR", status_code=500)


class DatabaseError(AppError):
    def __init__(
        self,
        message: str = "Database operation failed",
        *,
        code: str | None = None,
    ) -> None:
        super().__init__(message, code=code or "DATABASE_ERROR", status_code=500)
