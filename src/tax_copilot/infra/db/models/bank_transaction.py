"""통장(은행 계좌) 거래내역 한 건.

카드내역(CardTransaction)·세금계산서(TaxInvoice)와 함께 거래의 독립 입력원이며,
삼중 대사(통장 ↔ 카드 ↔ 세금계산서)의 기준이 된다. 입금/출금을 별도 컬럼으로
보관한다(은행 거래내역 엑셀의 일반적 형태).
"""

from datetime import date, datetime
from typing import Any

from sqlalchemy import JSON, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from tax_copilot.infra.db.models.base import Base


class BankTransaction(Base):
    """은행 통장 거래내역 한 줄."""

    __tablename__ = "bank_transactions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"), index=True)
    client_company_id: Mapped[int] = mapped_column(ForeignKey("client_companies.id"), index=True)
    uploaded_by: Mapped[int] = mapped_column(ForeignKey("users.id"))

    bank_name: Mapped[str | None] = mapped_column(String(40), nullable=True)
    account_no_masked: Mapped[str | None] = mapped_column(String(40), nullable=True)
    source_filename: Mapped[str] = mapped_column(String(255))

    transaction_date: Mapped[date | None] = mapped_column(nullable=True, index=True)
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)  # 적요/내용
    counterparty: Mapped[str | None] = mapped_column(String(255), nullable=True)
    deposit_krw: Mapped[int] = mapped_column(default=0, server_default="0")  # 입금
    withdrawal_krw: Mapped[int] = mapped_column(default=0, server_default="0")  # 출금
    balance_krw: Mapped[int | None] = mapped_column(nullable=True)  # 거래 후 잔액

    # 대사 결과 (reconciliation)
    matched: Mapped[bool] = mapped_column(default=False, server_default="false", index=True)
    matched_source_type: Mapped[str | None] = mapped_column(String(20), nullable=True)
    matched_source_id: Mapped[int | None] = mapped_column(nullable=True)

    raw_data: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)

    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        # tenant+거래처 내에서 동일 거래(일자+적요+금액+잔액) 중복 적재 방지.
        UniqueConstraint(
            "tenant_id",
            "client_company_id",
            "transaction_date",
            "description",
            "deposit_krw",
            "withdrawal_krw",
            "balance_krw",
            name="uq_bank_transactions_dedup",
        ),
    )
