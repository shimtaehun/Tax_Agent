from datetime import date, datetime

from pydantic import BaseModel


class TaxInvoiceItem(BaseModel):
    id: int
    client_company_id: int
    direction: str
    approval_no: str
    issue_date: date
    supplier_business_no: str | None
    supplier_name: str | None
    recipient_business_no: str | None
    recipient_name: str | None
    item_name: str | None
    supply_value_krw: int
    vat_krw: int
    total_amount_krw: int
    source_filename: str
    created_at: datetime


class TaxInvoiceListResponse(BaseModel):
    items: list[TaxInvoiceItem]
    total: int


class TaxInvoiceUploadResponse(BaseModel):
    imported_count: int
    skipped_count: int
    items: list[TaxInvoiceItem]


class TaxInvoiceUpdateRequest(BaseModel):
    direction: str | None = None
    approval_no: str | None = None
    issue_date: date | None = None
    supplier_business_no: str | None = None
    supplier_name: str | None = None
    recipient_business_no: str | None = None
    recipient_name: str | None = None
    item_name: str | None = None
    supply_value_krw: int | None = None
    vat_krw: int | None = None
    total_amount_krw: int | None = None
