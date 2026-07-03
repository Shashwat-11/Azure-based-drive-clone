from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKey


class Permission(Base, UUIDPrimaryKey, TimestampMixin):
    __tablename__ = "permissions"

    user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    resource_type: Mapped[str] = mapped_column(String(10), nullable=False)
    resource_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    granted_by: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    __table_args__ = (
        UniqueConstraint("user_id", "resource_type", "resource_id", name="uq_permission_user_resource"),
    )

    def __repr__(self) -> str:
        return f"<Permission(user={self.user_id}, {self.resource_type}={self.resource_id}, role={self.role})>"


class SharedLink(Base, UUIDPrimaryKey, TimestampMixin):
    __tablename__ = "shared_links"

    resource_type: Mapped[str] = mapped_column(String(10), nullable=False)
    resource_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False, index=True)
    token: Mapped[str] = mapped_column(String(128), unique=True, nullable=False, index=True)
    is_public: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true", nullable=False)
    password_hash: Mapped[str | None] = mapped_column(String(128), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    max_downloads: Mapped[int | None] = mapped_column(Integer, nullable=True)
    download_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0", nullable=False)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true", nullable=False)
    created_by: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )

    def is_expired(self) -> bool:
        from datetime import UTC
        if self.expires_at is None:
            return False
        return datetime.now(UTC) > self.expires_at

    def is_valid(self) -> bool:
        if not self.is_enabled:
            return False
        if self.is_expired():
            return False
        return not (self.max_downloads is not None and self.download_count >= self.max_downloads)

    def __repr__(self) -> str:
        return f"<SharedLink(token={self.token[:8]}..., {self.resource_type}={self.resource_id})>"
