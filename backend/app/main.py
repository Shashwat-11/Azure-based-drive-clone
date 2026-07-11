from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.responses import PlainTextResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.cors import CORSMiddleware

from app.api.v1 import router as v1_router
from app.config.settings import settings
from app.core.error_handlers import (
    app_error_handler,
    http_exception_handler,
    unhandled_exception_handler,
    validation_exception_handler,
)
from app.core.exceptions import AppError
from app.core.logging_config import configure_logging, get_logger
from app.core.otel import setup_otel, shutdown_otel
from app.dependencies.database import close_db
from app.dependencies.redis import close_redis
from app.middleware.correlation_id import CorrelationIdMiddleware
from app.middleware.metrics import MetricsMiddleware, get_metrics_text
from app.middleware.rate_limiter import RateLimiterMiddleware
from app.middleware.request_logger import RequestLoggerMiddleware
from app.middleware.security_headers import SecurityHeadersMiddleware
from app.middleware.timeout import RequestTimeoutMiddleware

# Override Starlette's default 1MB multipart part size limit.
# Starlette's Request.form() passes max_part_size=1MB explicitly to
# _get_form(), so we must override it at the _get_form level.
# Match the application's MAX_UPLOAD_SIZE_MB setting.
from starlette.requests import Request as _StarletteRequest

_original_get_form = _StarletteRequest._get_form

async def _patched_get_form(self, *,
                             max_files=1000, max_fields=1000,
                             max_part_size=None, **kwargs):
    return await _original_get_form(
        self, max_files=max_files, max_fields=max_fields,
        max_part_size=settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024,
        **kwargs)

_StarletteRequest._get_form = _patched_get_form

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    configure_logging(settings.LOG_LEVEL)
    setup_otel()
    logger.info(
        "application_starting",
        app_name=settings.APP_NAME,
        version=settings.APP_VERSION,
        environment=settings.ENVIRONMENT,
    )
    yield
    await close_db()
    await close_redis()
    shutdown_otel()
    logger.info("application_shutting_down")


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )

    _register_middleware(app)
    _register_exception_handlers(app)
    _register_routers(app)
    _register_metrics_endpoint(app)

    logger.info("application_created", routes=len(app.routes))
    return app


def _register_middleware(app: FastAPI) -> None:
    app.add_middleware(RequestTimeoutMiddleware)
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(CorrelationIdMiddleware)
    app.add_middleware(RequestLoggerMiddleware)
    app.add_middleware(RateLimiterMiddleware)
    app.add_middleware(MetricsMiddleware)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=settings.CORS_ALLOW_CREDENTIALS,
        allow_methods=settings.CORS_ALLOW_METHODS,
        allow_headers=settings.CORS_ALLOW_HEADERS,
    )


def _register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(AppError, app_error_handler)
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)


def _register_routers(app: FastAPI) -> None:
    app.include_router(v1_router)


def _register_metrics_endpoint(app: FastAPI) -> None:
    @app.get("/metrics", include_in_schema=False)
    async def metrics():
        return PlainTextResponse(content=get_metrics_text(), media_type="text/plain")


app = create_app()
