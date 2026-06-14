"""고객사 월마감 체크리스트 한 건 (고객사 × 연 × 월).

단계 목록은 JSON으로 보관한다(표준 템플릿 + 완료 상태). 진행률·전체 상태는
core/tax/monthly_closing.py 순수 함수로 계산한다.
"""

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from tax_copilot.infra.db.models.base import Base


class MonthlyClosing(Base):
    """고객사별 월 단위 마감 체크리스트."""

    __tablename__ = "monthly_closings"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"), index=True)
    client_company_id: Mapped[int] = mapped_column(ForeignKey("client_companies.id"), index=True)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))

    year: Mapped[int] = mapped_column(index=True)
    month: Mapped[int] = mapped_column(index=True)

    # [{key, label, done, done_at}, ...]
    steps: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    status: Mapped[str] = mapped_column(String(20), default="in_progress", index=True)

    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "client_company_id",
            "year",
            "month",
            name="uq_monthly_closings_tenant_company_period",
        ),
    )
