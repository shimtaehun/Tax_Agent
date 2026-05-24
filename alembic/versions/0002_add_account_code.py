"""add account_code to receipts

Revision ID: 0002
Revises: 0001
Create Date: 2026-05-24
"""

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "receipts",
        sa.Column("account_code", sa.String(length=20), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("receipts", "account_code")
