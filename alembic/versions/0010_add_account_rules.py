"""add account_rules table

Revision ID: 0010
Revises: 0009
Create Date: 2026-06-14
"""

import sqlalchemy as sa
from alembic import op

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "account_rules",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column(
            "client_company_id",
            sa.Integer(),
            sa.ForeignKey("client_companies.id"),
            nullable=True,
        ),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("match_type", sa.String(10), nullable=False, server_default="contains"),
        sa.Column("pattern", sa.String(255), nullable=False),
        sa.Column("account_code", sa.String(20), nullable=False),
        sa.Column("hit_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_account_rules_tenant_id", "account_rules", ["tenant_id"])
    op.create_index("ix_account_rules_client_company_id", "account_rules", ["client_company_id"])
    op.create_unique_constraint(
        "uq_account_rules_tenant_company_pattern",
        "account_rules",
        ["tenant_id", "client_company_id", "match_type", "pattern"],
    )


def downgrade() -> None:
    op.drop_table("account_rules")
