from datetime import date, datetime

from pydantic import BaseModel

from tax_copilot.core.tax.schemas import AccountCode


class ReceiptUploadResponse(BaseModel):
    receipt_id: int
    status: str
    message: str


class ReceiptStatusResponse(BaseModel):
    receipt_id: int
    status: str
    original_filename: str
    mime_type: str
    file_size_bytes: int
    client_company_id: int
    uploaded_by: int
    transaction_date: date | None
    parsed_data: dict | None
    langgraph_thread_id: str | None
    attempt_number: int
    error_message: str | None
    reviewed_by: int | None
    reviewed_at: datetime | None
    review_comment: str | None
    account_code: str | None = None
    account_code_reason: str | None = None
    duplicate_suspect: bool = False
    duplicate_receipt_ids: list[int] = []
    created_at: datetime
    updated_at: datetime


class ReceiptListResponse(BaseModel):
    items: list[ReceiptStatusResponse]
    total: int


class AccountCodeUpdateRequest(BaseModel):
    account_code: AccountCode


class BatchReceiptResult(BaseModel):
    filename: str
    receipt_id: int | None = None
    status: str  # "queued" | "skipped" | "error"
    reason: str | None = None


class BatchUploadResponse(BaseModel):
    batch_id: str
    total: int
    queued_count: int
    skipped_count: int
    error_count: int
    results: list[BatchReceiptResult]
