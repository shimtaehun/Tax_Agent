from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from tax_copilot.infra.db.models.base import Base, TimestampMixin

# 역할 목록: client (일반 사용자), staff (직원), admin (관리자)
ROLE_CLIENT = "client"
ROLE_STAFF = "staff"
ROLE_ADMIN = "admin"


class User(Base, TimestampMixin):
    """시스템 사용자. tenant 소속."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"), index=True)
    email: Mapped[str] = mapped_column(String(255), index=True)
    hashed_password: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(20), default=ROLE_CLIENT)
    is_active: Mapped[bool] = mapped_column(default=True)
    # client 역할 사용자가 속한 고객사 ID (staff/admin은 NULL)
    client_company_id: Mapped[int | None] = mapped_column(
        ForeignKey("client_companies.id"), default=None, nullable=True
    )

    __table_args__ = (UniqueConstraint("tenant_id", "email", name="uq_users_tenant_email"),)
