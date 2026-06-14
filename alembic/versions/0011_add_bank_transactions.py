"""add bank_transactions table

Revision ID: 0011
Revises: 0010
Create Date: 2026-06-14
"""

import sqlalchemy as sa
from alembic import op

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "bank_transactions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column(
            "client_company_id",
            sa.Integer(),
            sa.ForeignKey("client_companies.id"),
            nullable=False,
        ),
        sa.Column("uploaded_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("bank_name", sa.String(40), nullable=True),
        sa.Column("account_no_masked", sa.String(40), nullable=True),
        sa.Column("source_filename", sa.String(255), nullable=False),
        sa.Column("transaction_date", sa.Date(), nullable=True),
        sa.Column("description", sa.String(255), nullable=True),
        sa.Column("counterparty", sa.String(255), nullable=True),
        sa.Column("deposit_krw", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("withdrawal_krw", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("balance_krw", sa.Integer(), nullable=True),
        sa.Column("matched", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("matched_source_type", sa.String(20), nullable=True),
        sa.Column("matched_source_id", sa.Integer(), nullable=True),
        sa.Column("raw_data", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_bank_transactions_tenant_id", "bank_transactions", ["tenant_id"])
    op.create_index(
        "ix_bank_transactions_client_company_id", "bank_transactions", ["client_company_id"]
    )
    op.create_index(
        "ix_bank_transactions_transaction_date", "bank_transactions", ["transaction_date"]
    )
    op.create_index("ix_bank_transactions_matched", "bank_transactions", ["matched"])
    op.create_unique_constraint(
        "uq_bank_transactions_dedup",
        "bank_transactions",
        [
            "tenant_id",
            "client_company_id",
            "transaction_date",
            "description",
            "deposit_krw",
            "withdrawal_krw",
            "balance_krw",
        ],
    )


def downgrade() -> None:
    op.drop_table("bank_transactions")
