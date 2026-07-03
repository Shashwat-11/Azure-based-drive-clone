"""Add composite permission lookup index

Revision ID: 004
Revises: 003
Create Date: 2026-07-02

"""
from collections.abc import Sequence
from typing import Union

from alembic import op

revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index(
        "ix_permissions_resource_user",
        "permissions",
        ["resource_type", "resource_id", "user_id"],
    )
    op.create_index(
        "ix_shared_links_resource",
        "shared_links",
        ["resource_type", "resource_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_permissions_resource_user", table_name="permissions")
    op.drop_index("ix_shared_links_resource", table_name="shared_links")
