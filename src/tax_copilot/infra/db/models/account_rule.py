"""거래처별 계정과목 학습 규칙 (반복 거래 자동 분류).

세무사가 영수증/카드내역의 계정과목을 한 번 확정하면 규칙으로 저장되고,
이후 같은 가맹점 거래는 키워드 분류기보다 우선해 자동 분류된다.
client_company_id가 NULL이면 테넌트 전역 규칙으로 본다.
"""

from datetime import datetime

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from tax_copilot.infra.db.models.base import Base

MATCH_TYPE_EXACT = "exact"
MATCH_TYPE_CONTAINS = "contains"


class AccountRule(Base):
    """가맹점명 → 계정과목 학습 규칙."""

    __tablename__ = "account_rules"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"), index=True)
    # NULL = 테넌트 전역 규칙. 값이 있으면 해당 고객사 전용.
    client_company_id: Mapped[int | None] = mapped_column(
        ForeignKey("client_companies.id"), nullable=True, index=True
    )
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))

    match_type: Mapped[str] = mapped_column(String(10), default=MATCH_TYPE_CONTAINS)
    pattern: Mapped[str] = mapped_column(String(255))
    account_code: Mapped[str] = mapped_column(String(20))

    # 규칙이 실제로 자동 분류에 적용된 횟수 (효용 추적).
    hit_count: Mapped[int] = mapped_column(default=0, server_default="0")

    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "client_company_id",
            "match_type",
            "pattern",
            name="uq_account_rules_tenant_company_pattern",
        ),
    )
