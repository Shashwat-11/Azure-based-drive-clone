"""Create file_versions table

Revision ID: 005
Revises: 004
Create Date: 2026-07-03

"""
from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "005"
down_revision: Union[str, None] = "004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "file_versions",
        sa.Column(
            "id", postgresql.UUID(as_uuid=True), primary_key=True,
            server_default=sa.text("gen_random_uuid()"), nullable=False,
        ),
        sa.Column(
            "file_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("files.id", ondelete="CASCADE"), nullable=False, index=True,
        ),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("blob_name", sa.String(512), nullable=False),
        sa.Column("checksum_sha256", sa.String(64), nullable=False),
        sa.Column("mime_type", sa.String(255), nullable=True),
        sa.Column("extension", sa.String(64), nullable=True),
        sa.Column("file_size_bytes", sa.BigInteger(), default=0, nullable=False),
        sa.Column(
            "created_by", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True,
        ),
        sa.Column("etag", sa.String(128), nullable=True),
        sa.Column(
            "previous_version_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("file_versions.id", ondelete="SET NULL"), nullable=True,
        ),
        sa.Column("is_current", sa.Boolean(), default=False, nullable=False, index=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_file_versions_file_version", "file_versions", ["file_id", "version_number"])


def downgrade() -> None:
    op.drop_table("file_versions")
