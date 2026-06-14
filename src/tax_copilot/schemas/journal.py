from datetime import date

from pydantic import BaseModel


class JournalLineOut(BaseModel):
    side: str  # "차변" | "대변"
    account_title: str
    amount_krw: int
    description: str | None = None


class JournalEntryOut(BaseModel):
    entry_date: date
    summary: str
    source_type: str
    source_id: int | None = None
    counterparty: str | None = None
    debit_total: int
    credit_total: int
    balanced: bool
    lines: list[JournalLineOut]


class JournalPreviewResponse(BaseModel):
    client_company_id: int
    from_date: date
    to_date: date
    entry_count: int
    debit_total: int
    credit_total: int
    balanced: bool
    items: list[JournalEntryOut]
