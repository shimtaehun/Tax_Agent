from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from tax_copilot.infra.db.models.base import Base, TimestampMixin


class ClientCompany(Base, TimestampMixin):
    """세무사 사무소의 고객사 (블루문, 선샤인 등)."""

    __tablename__ = "client_companies"

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"), index=True)
    name: Mapped[str] = mapped_column(String(255))
    # 사업자등록번호 — 로그 출력 시 마스킹 대상
    business_no: Mapped[str | None] = mapped_column(String(20), nullable=True)
    is_active: Mapped[bool] = mapped_column(default=True)

    __table_args__ = (
        UniqueConstraint("tenant_id", "business_no", name="uq_client_companies_tenant_bno"),
    )
