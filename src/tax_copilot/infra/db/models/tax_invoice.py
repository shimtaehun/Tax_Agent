from datetime import date, datetime

from sqlalchemy import JSON, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from tax_copilot.infra.db.models.base import Base

INVOICE_DIRECTION_SALE = "SALE"
INVOICE_DIRECTION_PURCHASE = "PURCHASE"


class TaxInvoice(Base):
    """Hometax electronic tax invoice imported from XML/CSV exports."""

    __tablename__ = "tax_invoices"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"), index=True)
    client_company_id: Mapped[int] = mapped_column(ForeignKey("client_companies.id"), index=True)
    uploaded_by: Mapped[int] = mapped_column(ForeignKey("users.id"))

    direction: Mapped[str] = mapped_column(String(20), index=True)
    approval_no: Mapped[str] = mapped_column(String(80))
    issue_date: Mapped[date] = mapped_column(index=True)
    supplier_business_no: Mapped[str | None] = mapped_column(String(20), nullable=True)
    supplier_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    recipient_business_no: Mapped[str | None] = mapped_column(String(20), nullable=True)
    recipient_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    item_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    supply_value_krw: Mapped[int] = mapped_column(default=0)
    vat_krw: Mapped[int] = mapped_column(default=0)
    total_amount_krw: Mapped[int] = mapped_column(default=0)
    source_filename: Mapped[str] = mapped_column(String(255))
    raw_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "client_company_id",
            "approval_no",
            name="uq_tax_invoices_tenant_company_approval",
        ),
    )
