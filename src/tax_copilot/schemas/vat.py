from datetime import date

from pydantic import BaseModel


class VatGroup(BaseModel):
    supply_value_krw: int
    vat_krw: int
    receipt_count: int


class AccountCodeSummary(BaseModel):
    account_code: str
    supply_value_krw: int
    vat_krw: int
    receipt_count: int


class VatSummaryResponse(BaseModel):
    client_company_id: int
    from_date: date
    to_date: date
    creditable: VatGroup
    non_creditable: VatGroup
    pending_review_count: int
    by_account_code: list[AccountCodeSummary]
