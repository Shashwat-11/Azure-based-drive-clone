from __future__ import annotations

from functools import lru_cache
from typing import Literal
from urllib.parse import quote

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import URL


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Application
    APP_NAME: str = "Drive"
    APP_VERSION: str = "0.1.0"
    ENVIRONMENT: Literal["development", "staging", "production"] = "development"
    DEBUG: bool = False
    LOG_LEVEL: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"

    # Server
    HOST: str = "0.0.0.0"  # nosec B104 — deployed in Docker/Azure, not exposed to raw network
    PORT: int = 8000
    WORKERS: int = 1

    # CORS
    CORS_ORIGINS: list[str] = Field(default_factory=lambda: ["http://localhost:3000"])
    CORS_ALLOW_CREDENTIALS: bool = True
    CORS_ALLOW_METHODS: list[str] = Field(default_factory=lambda: ["*"])
    CORS_ALLOW_HEADERS: list[str] = Field(default_factory=lambda: ["*"])

    # Database
    DB_HOST: str = "localhost"
    DB_PORT: int = Field(default=5432, ge=1, le=65535)
    DB_USER: str = "drive"
    DB_PASSWORD: SecretStr = SecretStr("drive")
    DB_NAME: str = "drive"
    DB_POOL_SIZE: int = Field(default=20, ge=1, le=100)
    DB_POOL_OVERFLOW: int = Field(default=10, ge=0)
    DB_POOL_TIMEOUT: int = Field(default=30, ge=1)
    DB_ECHO: bool = False

    @property
    def DATABASE_URL(self) -> str:  # noqa: N802
        return URL.create(
            "postgresql+asyncpg",
            username=self.DB_USER,
            password=self.DB_PASSWORD.get_secret_value(),
            host=self.DB_HOST,
            port=self.DB_PORT,
            database=self.DB_NAME,
        ).render_as_string(hide_password=False)

    @property
    def DATABASE_URL_SYNC(self) -> str:  # noqa: N802
        return URL.create(
            "postgresql+psycopg2",
            username=self.DB_USER,
            password=self.DB_PASSWORD.get_secret_value(),
            host=self.DB_HOST,
            port=self.DB_PORT,
            database=self.DB_NAME,
        ).render_as_string(hide_password=False)

    # Redis
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = Field(default=6379, ge=1, le=65535)
    REDIS_DB: int = 0
    REDIS_PASSWORD: SecretStr | None = None
    REDIS_SSL: bool = False
    REDIS_POOL_SIZE: int = Field(default=10, ge=1)

    @property
    def REDIS_URL(self) -> str:  # noqa: N802
        scheme = "rediss" if self.REDIS_SSL else "redis"
        if self.REDIS_PASSWORD:
            pw = quote(self.REDIS_PASSWORD.get_secret_value(), safe="")
            return f"{scheme}://:{pw}@{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"
        return f"{scheme}://{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"

    # Azure Blob Storage
    AZURE_STORAGE_ACCOUNT_NAME: str | None = None
    AZURE_STORAGE_ACCOUNT_KEY: SecretStr | None = None
    AZURE_STORAGE_CONNECTION_STRING: SecretStr | None = None
    AZURE_STORAGE_CONTAINER_NAME: str = "drive-files"
    AZURE_STORAGE_USE_AZURITE: bool = False
    AZURE_STORAGE_AZURITE_URL: str = "http://localhost:10000"

    @property
    def AZURE_STORAGE_ENABLED(self) -> bool:  # noqa: N802
        return self.AZURE_STORAGE_CONNECTION_STRING is not None or (
            self.AZURE_STORAGE_ACCOUNT_NAME is not None
            and self.AZURE_STORAGE_ACCOUNT_KEY is not None
        )

    # JWT
    JWT_SECRET_KEY: SecretStr = SecretStr("change-me-in-production-use-azure-key-vault")
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=30, ge=1)
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = Field(default=7, ge=1)
    JWT_ISSUER: str = "drive-api"

    # Rate Limiting
    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_REQUESTS: int = Field(default=100, ge=1)
    RATE_LIMIT_WINDOW_SECONDS: int = Field(default=60, ge=1)

    # File Upload
    MAX_UPLOAD_SIZE_MB: int = Field(default=100, ge=1, le=10240)
    ALLOWED_UPLOAD_EXTENSIONS: list[str] | None = None

    # Security
    SECURE_HEADERS_ENABLED: bool = True
    TRUSTED_PROXY_COUNT: int = Field(default=0, ge=0)

    # Observability
    METRICS_ENABLED: bool = True
    OTEL_ENABLED: bool = False
    OTEL_SAMPLING_RATE: float = Field(default=0.1, ge=0.0, le=1.0)
    AZURE_APPINSIGHTS_CONNECTION_STRING: str | None = None
    REQUEST_TIMEOUT_SECONDS: int = Field(default=60, ge=1)

    @field_validator("LOG_LEVEL", mode="before")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        return v.upper()

    @field_validator("ENVIRONMENT", mode="before")
    @classmethod
    def validate_environment(cls, v: str) -> str:
        return v.lower()

    @model_validator(mode="after")
    def validate_production_secrets(self) -> Settings:
        if self.ENVIRONMENT != "production":
            return self
        if self.JWT_SECRET_KEY.get_secret_value() == "change-me-in-production-use-azure-key-vault":
            raise ValueError(
                "JWT_SECRET_KEY must be overridden in production"
            )
        if self.DB_PASSWORD.get_secret_value() == "drive":
            raise ValueError(
                "DB_PASSWORD must be overridden in production"
            )
        if self.RATE_LIMIT_ENABLED and self.REDIS_PASSWORD is None:
            import logging
            logging.getLogger("drive").warning(
                "REDIS_PASSWORD is not set — rate limiting disabled. "
                "Redis-backed features will be unavailable. "
                "Set REDIS_PASSWORD or configure Entra ID authentication."
            )
            object.__setattr__(self, "RATE_LIMIT_ENABLED", False)
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
