from __future__ import annotations

import uuid
from typing import Any

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.exceptions import AppError
from app.core.logging_config import get_logger

logger = get_logger(__name__)


def _build_error_response(
    status_code: int,
    message: str,
    *,
    code: str = "INTERNAL_ERROR",
    details: dict[str, Any] | None = None,
    trace_id: str | None = None,
) -> JSONResponse:
    trace_id = trace_id or str(uuid.uuid4())
    content: dict[str, Any] = {
        "success": False,
        "message": message,
        "code": code,
        "trace_id": trace_id,
    }
    if details:
        content["details"] = details
    return JSONResponse(status_code=status_code, content=content)


async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    trace_id = getattr(request.state, "trace_id", None)
    logger.error(
        "application_error",
        message=exc.message,
        code=exc.code,
        status_code=exc.status_code,
        path=request.url.path,
        method=request.method,
        details=exc.details,
        trace_id=trace_id,
    )
    return _build_error_response(
        status_code=exc.status_code,
        message=exc.message,
        code=exc.code,
        details=exc.details,
        trace_id=trace_id,
    )


async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    trace_id = getattr(request.state, "trace_id", None)
    logger.warning(
        "http_exception",
        status_code=exc.status_code,
        detail=str(exc.detail),
        path=request.url.path,
        method=request.method,
        trace_id=trace_id,
    )
    mapping: dict[int, str] = {
        400: "BAD_REQUEST",
        401: "AUTHENTICATION_REQUIRED",
        403: "FORBIDDEN",
        404: "NOT_FOUND",
        405: "METHOD_NOT_ALLOWED",
        409: "CONFLICT",
        429: "RATE_LIMIT_EXCEEDED",
        500: "INTERNAL_ERROR",
        502: "BAD_GATEWAY",
        503: "SERVICE_UNAVAILABLE",
        504: "GATEWAY_TIMEOUT",
    }
    return _build_error_response(
        status_code=exc.status_code,
        message=str(exc.detail),
        code=mapping.get(exc.status_code, "HTTP_ERROR"),
        trace_id=trace_id,
    )


async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    trace_id = getattr(request.state, "trace_id", None)
    details = exc.errors()
    logger.warning(
        "validation_error",
        errors=details,
        path=request.url.path,
        method=request.method,
        trace_id=trace_id,
    )
    return _build_error_response(
        status_code=422,
        message="Request validation failed",
        code="VALIDATION_ERROR",
        details={"errors": details},
        trace_id=trace_id,
    )


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    trace_id = getattr(request.state, "trace_id", None)
    logger.exception(
        "unhandled_exception",
        exception_type=type(exc).__name__,
        path=request.url.path,
        method=request.method,
        trace_id=trace_id,
    )
    return _build_error_response(
        status_code=500,
        message="An unexpected error occurred",
        code="INTERNAL_ERROR",
        trace_id=trace_id,
    )
