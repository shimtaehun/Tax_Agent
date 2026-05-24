"""add batch_id column to receipts

Revision ID: 0004
Revises: 0003
Create Date: 2026-05-25
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "receipts",
        sa.Column("batch_id", sa.String(36), nullable=True, index=True),
    )


def downgrade() -> None:
    op.drop_column("receipts", "batch_id")
