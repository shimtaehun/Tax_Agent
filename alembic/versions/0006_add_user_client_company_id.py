"""add client_company_id to users

Revision ID: 0006
Revises: 0005
Create Date: 2026-05-25
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("users", sa.Column("client_company_id", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "client_company_id")
