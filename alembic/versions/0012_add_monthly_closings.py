"""add monthly_closings table

Revision ID: 0012
Revises: 0011
Create Date: 2026-06-14
"""

import sqlalchemy as sa
from alembic import op

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "monthly_closings",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column(
            "client_company_id",
            sa.Integer(),
            sa.ForeignKey("client_companies.id"),
            nullable=False,
        ),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("month", sa.Integer(), nullable=False),
        sa.Column("steps", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="in_progress"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_monthly_closings_tenant_id", "monthly_closings", ["tenant_id"])
    op.create_index(
        "ix_monthly_closings_client_company_id", "monthly_closings", ["client_company_id"]
    )
    op.create_index("ix_monthly_closings_year", "monthly_closings", ["year"])
    op.create_index("ix_monthly_closings_month", "monthly_closings", ["month"])
    op.create_index("ix_monthly_closings_status", "monthly_closings", ["status"])
    op.create_unique_constraint(
        "uq_monthly_closings_tenant_company_period",
        "monthly_closings",
        ["tenant_id", "client_company_id", "year", "month"],
    )


def downgrade() -> None:
    op.drop_table("monthly_closings")
