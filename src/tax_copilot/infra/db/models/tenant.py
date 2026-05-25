from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from tax_copilot.infra.db.models.base import Base, TimestampMixin


class Tenant(Base, TimestampMixin):
    """세무사 사무소 또는 세무법인 단위."""

    __tablename__ = "tenants"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(default=True)
