"""add filing_deadlines table

Revision ID: 0005
Revises: 0004
Create Date: 2026-05-25
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "filing_deadlines",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column(
            "client_company_id",
            sa.Integer(),
            sa.ForeignKey("client_companies.id"),
            nullable=False,
        ),
        sa.Column("tax_type", sa.String(30), nullable=False),
        sa.Column("fiscal_year", sa.Integer(), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=False),
        sa.Column("description", sa.String(100), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("completed_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint(
            "tenant_id",
            "client_company_id",
            "fiscal_year",
            "tax_type",
            name="uq_filing_deadline",
        ),
    )
    op.create_index("ix_filing_deadlines_tenant_id", "filing_deadlines", ["tenant_id"])
    op.create_index(
        "ix_filing_deadlines_client_company_id", "filing_deadlines", ["client_company_id"]
    )


def downgrade() -> None:
    op.drop_table("filing_deadlines")
