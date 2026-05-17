from datetime import date, time
from typing import Literal

from pydantic import BaseModel, Field

EvidenceType = Literal[
    "tax_invoice",
    "invoice",
    "credit_card_slip",
    "cash_receipt",
    "simplified_receipt",
    "unknown",
]


class Citation(BaseModel):
    chunk_id: str
    law_name: str
    article_no: str | None = None
    paragraph_no: str | None = None
    effective_from: date
    effective_to: date | None = None
    quoted_text: str


class TaxDecision(BaseModel):
    vat_creditable: bool | None = Field(
        default=None,
        description="VAT input tax credit eligibility. None = cannot determine.",
    )
    expense_deductible: bool | None = Field(
        default=None,
        description="Corporate income tax deductibility or necessary expense eligibility.",
    )
    account_title: str | None = Field(
        default=None,
        description="Account title candidate (e.g., 접대비, 복리후생비, 소모품비).",
    )
    evidence_type: EvidenceType
    evidence_status: Literal["valid", "insufficient", "unreadable", "unknown"]
    confidence: float = Field(ge=0.0, le=1.0)
    risk_flags: list[str] = []
    citations: list[Citation] = []
    requires_human_review: bool
    review_reason: str | None = None
    prompt_version: str
    model_name: str
    law_corpus_version: str


class ParsedReceipt(BaseModel):
    merchant_name: str | None = None
    merchant_business_no: str | None = None
    transaction_date: date | None = None
    transaction_time: time | None = None
    total_amount_krw: int | None = None
    supply_value_krw: int | None = None
    vat_amount_krw: int | None = None
    items: list[str] = []
    payment_method: str | None = None
    evidence_type: EvidenceType = "unknown"
    raw_ocr_text: str | None = None
