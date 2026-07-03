from __future__ import annotations

import uuid

from sqlalchemy import (
    JSON,
    BigInteger,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, SoftDeleteMixin, TimestampMixin, UUIDPrimaryKey
from app.models.versioning import FileVersion


class Folder(Base, UUIDPrimaryKey, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "folders"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("folders.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    owner_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    parent: Mapped[Folder | None] = relationship(
        "Folder", remote_side="Folder.id", back_populates="children"
    )
    children: Mapped[list[Folder]] = relationship(
        "Folder", back_populates="parent", cascade="all, delete-orphan"
    )
    files: Mapped[list[File]] = relationship(
        "File", back_populates="folder", cascade="all, delete-orphan"
    )

    __table_args__ = (
        UniqueConstraint(
            "name", "parent_id", "owner_id",
            name="uq_folder_name_parent_owner",
        ),
        Index("ix_folders_parent_id_created_at", "parent_id", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<Folder(id={self.id}, name={self.name}, owner_id={self.owner_id})>"


class File(Base, UUIDPrimaryKey, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "files"

    owner_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    folder_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("folders.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    folder: Mapped[Folder | None] = relationship("Folder", back_populates="files")
    versions: Mapped[list[FileVersion]] = relationship(
        "FileVersion", back_populates="file", cascade="all, delete-orphan"
    )

    original_filename: Mapped[str] = mapped_column(String(1024), nullable=False)
    stored_blob_name: Mapped[str] = mapped_column(String(512), nullable=False)
    mime_type: Mapped[str | None] = mapped_column(String(255), nullable=True)
    extension: Mapped[str | None] = mapped_column(String(64), nullable=True)
    checksum_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    file_size_bytes: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    storage_provider: Mapped[str] = mapped_column(
        String(50), default="azure", server_default="azure", nullable=False
    )
    etag: Mapped[str | None] = mapped_column(String(128), nullable=True)
    version_number: Mapped[int] = mapped_column(
        Integer, default=1, server_default="1", nullable=False
    )
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    color_label: Mapped[str | None] = mapped_column(String(20), nullable=True)
    custom_properties: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    __table_args__ = (
        Index("ix_files_folder_id_created_at", "folder_id", "created_at"),
        Index("ix_files_owner_id_created_at", "owner_id", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<File(id={self.id}, name={self.original_filename}, owner_id={self.owner_id})>"
