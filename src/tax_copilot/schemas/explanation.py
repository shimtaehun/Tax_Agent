from datetime import date, datetime
from typing import Any

from pydantic import BaseModel


class CitationResponse(BaseModel):
    chunk_id: str
    law_name: str
    article_no: str | None
    paragraph_no: str | None
    effective_from: date
    effective_to: date | None
    quoted_text: str


class DecisionSummary(BaseModel):
    vat_creditable: bool | None
    expense_deductible: bool | None
    account_code: str | None
    account_code_reason: str | None
    evidence_type: str
    evidence_status: str
    confidence: float
    prompt_version: str
    model_name: str
    law_corpus_version: str
    calculation_result: dict[str, Any] | None
    human_approved: bool | None
    human_comment: str | None


class AuditEvent(BaseModel):
    event_type: str
    actor_user_id: int | None
    created_at: datetime
    payload: dict[str, Any] | None


class ExplanationResponse(BaseModel):
    receipt_id: int
    status: str
    decision: DecisionSummary | None
    citations: list[CitationResponse]
    risk_flags: list[str]
    audit_trail: list[AuditEvent]
