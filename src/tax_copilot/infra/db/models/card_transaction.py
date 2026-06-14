"""카드사 결제내역 엑셀에서 적재한 거래 한 건.

세금계산서 import(TaxInvoice)와 동일한 단일 평면 테이블 패턴을 따른다 —
엑셀 한 행 = 한 거래 = 한 레코드. 영수증(Receipt)과 함께 거래의 독립 입력원이며,
이 단계에서는 영수증과의 매칭은 다루지 않는다.
"""

from datetime import date, datetime, time
from typing import Any

from sqlalchemy import JSON, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from tax_copilot.infra.db.models.base import Base

# 처리 상태 — 영수증과 동일한 어휘를 쓴다.
STATUS_PENDING = "PENDING"
STATUS_NEEDS_REVIEW = "NEEDS_REVIEW"
STATUS_APPROVED = "APPROVED"
STATUS_REJECTED = "REJECTED"


class CardTransaction(Base):
    """카드사 엑셀 결제목록에서 적재한 개별 거래."""

    __tablename__ = "card_transactions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"), index=True)
    client_company_id: Mapped[int] = mapped_column(ForeignKey("client_companies.id"), index=True)
    uploaded_by: Mapped[int] = mapped_column(ForeignKey("users.id"))

    card_company: Mapped[str] = mapped_column(String(40), index=True)
    source_filename: Mapped[str] = mapped_column(String(255))

    # 거래 정보 (정규화된 StatementRow에서 옮겨온다)
    transaction_date: Mapped[date | None] = mapped_column(nullable=True, index=True)
    transaction_time: Mapped[time | None] = mapped_column(nullable=True)
    merchant_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    approval_no: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    card_no_masked: Mapped[str | None] = mapped_column(String(40), nullable=True)
    total_amount_krw: Mapped[int | None] = mapped_column(nullable=True)
    supply_value_krw: Mapped[int | None] = mapped_column(nullable=True)
    vat_krw: Mapped[int | None] = mapped_column(nullable=True)
    installment_months: Mapped[int | None] = mapped_column(nullable=True)
    category: Mapped[str | None] = mapped_column(String(100), nullable=True)
    currency: Mapped[str] = mapped_column(String(8), default="KRW")
    cancelled: Mapped[bool] = mapped_column(default=False, server_default="false")

    # 계정과목 분류 결과 (영수증과 동일한 후속 파이프라인 진입점)
    account_code: Mapped[str | None] = mapped_column(String(20), nullable=True)

    status: Mapped[str] = mapped_column(String(30), default=STATUS_PENDING, index=True)
    raw_data: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)

    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        # tenant+거래처 내에서 동일 승인번호 중복 적재 방지.
        UniqueConstraint(
            "tenant_id",
            "client_company_id",
            "approval_no",
            name="uq_card_transactions_tenant_company_approval",
        ),
    )
