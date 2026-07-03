"""Add metadata columns to files and create discovery tables

Revision ID: 006
Revises: 005
Create Date: 2026-07-03

"""
from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "006"
down_revision: Union[str, None] = "005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("files", sa.Column("description", sa.Text(), nullable=True))
    op.add_column("files", sa.Column("color_label", sa.String(20), nullable=True))
    op.add_column("files", sa.Column("custom_properties", postgresql.JSONB(), nullable=True))

    op.create_table(
        "tags",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("user_id", "name", name="uq_tag_user_name"),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "file_tags",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("file_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("files.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("tag_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("tags.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.UniqueConstraint("file_id", "tag_id", name="uq_file_tag"),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "favorites",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("file_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("files.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("user_id", "file_id", name="uq_favorite_user_file"),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "recent_files",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("file_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("files.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("action_type", sa.String(20), nullable=False),
        sa.Column("accessed_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False, index=True),
        sa.UniqueConstraint("user_id", "file_id", "action_type", name="uq_recent_user_file_action"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_recent_user_accessed", "recent_files", ["user_id", "accessed_at"])


def downgrade() -> None:
    op.drop_table("recent_files")
    op.drop_table("favorites")
    op.drop_table("file_tags")
    op.drop_table("tags")
    op.drop_column("files", "custom_properties")
    op.drop_column("files", "color_label")
    op.drop_column("files", "description")
