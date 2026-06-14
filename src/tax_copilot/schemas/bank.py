from datetime import date, datetime

from pydantic import BaseModel


class BankTransactionItem(BaseModel):
    id: int
    client_company_id: int
    bank_name: str | None
    account_no_masked: str | None
    transaction_date: date | None
    description: str | None
    counterparty: str | None
    deposit_krw: int
    withdrawal_krw: int
    balance_krw: int | None
    matched: bool
    matched_source_type: str | None
    matched_source_id: int | None
    source_filename: str
    created_at: datetime


class BankUploadResponse(BaseModel):
    imported_count: int
    skipped_count: int
    items: list[BankTransactionItem]


class BankListResponse(BaseModel):
    items: list[BankTransactionItem]
    total: int


class ReconMatchItem(BaseModel):
    bank_id: int
    source_type: str
    source_id: int
    amount_krw: int


class ReconUnmatchedCandidate(BaseModel):
    source_type: str
    source_id: int
    amount_krw: int
    transaction_date: date | None
    direction: str
    label: str | None


class ReconciliationResponse(BaseModel):
    client_company_id: int
    from_date: date
    to_date: date
    bank_count: int
    candidate_count: int
    matched_count: int
    matches: list[ReconMatchItem]
    # 근거 없는 입출금 (통장엔 있으나 카드·계산서 근거 없음)
    unmatched_bank: list[BankTransactionItem]
    # 통장 미반영 (카드·계산서엔 있으나 통장 출입금 없음)
    unmatched_candidates: list[ReconUnmatchedCandidate]
