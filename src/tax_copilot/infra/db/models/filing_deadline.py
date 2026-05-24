from datetime import date, datetime

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from tax_copilot.infra.db.models.base import Base

DEADLINE_STATUS_PENDING = "pending"
DEADLINE_STATUS_COMPLETED = "completed"
DEADLINE_STATUS_OVERDUE = "overdue"


class FilingDeadline(Base):
    """세금 신고 기한."""

    __tablename__ = "filing_deadlines"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"), index=True)
    client_company_id: Mapped[int] = mapped_column(ForeignKey("client_companies.id"), index=True)

    tax_type: Mapped[str] = mapped_column(String(30))
    fiscal_year: Mapped[int]
    due_date: Mapped[date]
    description: Mapped[str] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(20), default=DEADLINE_STATUS_PENDING)

    completed_at: Mapped[datetime | None] = mapped_column(nullable=True)
    completed_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)

    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)

    __table_args__ = (
        # 같은 회사의 같은 연도·세금 종류 중복 방지
        UniqueConstraint(
            "tenant_id",
            "client_company_id",
            "fiscal_year",
            "tax_type",
            name="uq_filing_deadline",
        ),
    )
