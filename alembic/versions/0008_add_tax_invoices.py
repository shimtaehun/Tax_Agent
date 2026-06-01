"""add tax_invoices table

Revision ID: 0008
Revises: 0007
Create Date: 2026-05-31
"""

import sqlalchemy as sa
from alembic import op

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "tax_invoices",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column(
            "client_company_id",
            sa.Integer(),
            sa.ForeignKey("client_companies.id"),
            nullable=False,
        ),
        sa.Column("uploaded_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("direction", sa.String(20), nullable=False),
        sa.Column("approval_no", sa.String(80), nullable=False),
        sa.Column("issue_date", sa.Date(), nullable=False),
        sa.Column("supplier_business_no", sa.String(20), nullable=True),
        sa.Column("supplier_name", sa.String(255), nullable=True),
        sa.Column("recipient_business_no", sa.String(20), nullable=True),
        sa.Column("recipient_name", sa.String(255), nullable=True),
        sa.Column("item_name", sa.String(255), nullable=True),
        sa.Column("supply_value_krw", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("vat_krw", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_amount_krw", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("source_filename", sa.String(255), nullable=False),
        sa.Column("raw_data", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_tax_invoices_tenant_id", "tax_invoices", ["tenant_id"])
    op.create_index("ix_tax_invoices_client_company_id", "tax_invoices", ["client_company_id"])
    op.create_index("ix_tax_invoices_direction", "tax_invoices", ["direction"])
    op.create_index("ix_tax_invoices_issue_date", "tax_invoices", ["issue_date"])
    op.create_unique_constraint(
        "uq_tax_invoices_tenant_company_approval",
        "tax_invoices",
        ["tenant_id", "client_company_id", "approval_no"],
    )


def downgrade() -> None:
    op.drop_table("tax_invoices")
