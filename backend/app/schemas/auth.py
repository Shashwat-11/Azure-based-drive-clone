from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.core.logging_config import get_logger

logger = get_logger(__name__)


class RegisterRequest(BaseModel):
    email: EmailStr = Field(..., max_length=320)
    password: str = Field(..., min_length=8, max_length=128)
    full_name: str = Field(..., min_length=1, max_length=255)

    @field_validator("email", mode="before")
    @classmethod
    def log_email_before_validation(cls, v: str) -> str:
        logger.debug("register_request_validating_email_enter", email=v)
        return v

    @field_validator("email", mode="after")
    @classmethod
    def log_email_after_validation(cls, v: str) -> str:
        logger.debug("register_request_validating_email_complete", email=v)
        return v

    def model_post_init(self, _context: object) -> None:
        logger.debug("register_request_fully_validated", email=self.email)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    full_name: str
    role: str
    is_active: bool
    is_verified: bool
    created_at: datetime
    updated_at: datetime


class LogoutRequest(BaseModel):
    refresh_token: str


class MessageResponse(BaseModel):
    success: bool
    message: str
    code: str
