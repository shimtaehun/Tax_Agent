"""add card_transactions table

Revision ID: 0009
Revises: 0008
Create Date: 2026-06-11
"""

import sqlalchemy as sa
from alembic import op

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "card_transactions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column(
            "client_company_id",
            sa.Integer(),
            sa.ForeignKey("client_companies.id"),
            nullable=False,
        ),
        sa.Column("uploaded_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("card_company", sa.String(40), nullable=False),
        sa.Column("source_filename", sa.String(255), nullable=False),
        sa.Column("transaction_date", sa.Date(), nullable=True),
        sa.Column("transaction_time", sa.Time(), nullable=True),
        sa.Column("merchant_name", sa.String(255), nullable=True),
        sa.Column("approval_no", sa.String(80), nullable=True),
        sa.Column("card_no_masked", sa.String(40), nullable=True),
        sa.Column("total_amount_krw", sa.Integer(), nullable=True),
        sa.Column("supply_value_krw", sa.Integer(), nullable=True),
        sa.Column("vat_krw", sa.Integer(), nullable=True),
        sa.Column("installment_months", sa.Integer(), nullable=True),
        sa.Column("category", sa.String(100), nullable=True),
        sa.Column("currency", sa.String(8), nullable=False, server_default="KRW"),
        sa.Column("cancelled", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("account_code", sa.String(20), nullable=True),
        sa.Column("status", sa.String(30), nullable=False, server_default="PENDING"),
        sa.Column("raw_data", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_card_transactions_tenant_id", "card_transactions", ["tenant_id"])
    op.create_index(
        "ix_card_transactions_client_company_id", "card_transactions", ["client_company_id"]
    )
    op.create_index("ix_card_transactions_card_company", "card_transactions", ["card_company"])
    op.create_index(
        "ix_card_transactions_transaction_date", "card_transactions", ["transaction_date"]
    )
    op.create_index("ix_card_transactions_approval_no", "card_transactions", ["approval_no"])
    op.create_index("ix_card_transactions_status", "card_transactions", ["status"])
    op.create_unique_constraint(
        "uq_card_transactions_tenant_company_approval",
        "card_transactions",
        ["tenant_id", "client_company_id", "approval_no"],
    )


def downgrade() -> None:
    op.drop_table("card_transactions")
