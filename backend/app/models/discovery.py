from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKey


class Tag(Base, UUIDPrimaryKey, TimestampMixin):
    __tablename__ = "tags"

    user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)

    __table_args__ = (
        UniqueConstraint("user_id", "name", name="uq_tag_user_name"),
    )

    def __repr__(self) -> str:
        return f"<Tag(id={self.id}, name={self.name})>"


class FileTag(Base, UUIDPrimaryKey):
    __tablename__ = "file_tags"

    file_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("files.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    tag_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("tags.id", ondelete="CASCADE"), nullable=False, index=True,
    )

    __table_args__ = (
        UniqueConstraint("file_id", "tag_id", name="uq_file_tag"),
    )

    def __repr__(self) -> str:
        return f"<FileTag(file={self.file_id}, tag={self.tag_id})>"


class Favorite(Base, UUIDPrimaryKey):
    __tablename__ = "favorites"

    user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    file_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("files.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )

    __table_args__ = (
        UniqueConstraint("user_id", "file_id", name="uq_favorite_user_file"),
    )

    def __repr__(self) -> str:
        return f"<Favorite(user={self.user_id}, file={self.file_id})>"


class RecentFile(Base, UUIDPrimaryKey):
    __tablename__ = "recent_files"

    user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    file_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("files.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    action_type: Mapped[str] = mapped_column(String(20), nullable=False)
    accessed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True,
    )

    __table_args__ = (
        UniqueConstraint("user_id", "file_id", "action_type", name="uq_recent_user_file_action"),
        Index("ix_recent_user_accessed", "user_id", "accessed_at"),
    )

    def __repr__(self) -> str:
        return f"<RecentFile(user={self.user_id}, file={self.file_id}, action={self.action_type})>"
