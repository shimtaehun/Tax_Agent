from datetime import date, datetime, time

from pydantic import BaseModel


class StatementUploadResponse(BaseModel):
    card_company: str
    imported_count: int
    skipped_count: int
    total_count: int


class StatementTransactionItem(BaseModel):
    id: int
    client_company_id: int
    card_company: str
    transaction_date: date | None
    transaction_time: time | None
    merchant_name: str | None
    approval_no: str | None
    card_no_masked: str | None
    total_amount_krw: int | None
    installment_months: int | None
    account_code: str | None
    cancelled: bool
    status: str
    source_filename: str
    created_at: datetime


class StatementListResponse(BaseModel):
    items: list[StatementTransactionItem]
    total: int
