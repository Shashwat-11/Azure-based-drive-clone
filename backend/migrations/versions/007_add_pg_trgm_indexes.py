"""Enable pg_trgm and add GIN trigram index

Revision ID: 007
Revises: 006
Create Date: 2026-07-03

"""
from collections.abc import Sequence
from typing import Union

from alembic import op

revision: str = "007"
down_revision: Union[str, None] = "006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    op.execute("""
    CREATE INDEX IF NOT EXISTS ix_files_filename_trgm
    ON files USING gin (original_filename gin_trgm_ops)
    """)

    op.execute("""
    CREATE INDEX IF NOT EXISTS ix_files_description_trgm
    ON files USING gin (description gin_trgm_ops)
    """)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_files_description_trgm")
    op.execute("DROP INDEX IF EXISTS ix_files_filename_trgm")
