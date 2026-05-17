from datetime import date
from typing import Any, Literal, TypedDict

WorkflowStatus = Literal[
    "PENDING",
    "PROCESSING",
    "AWAITING_REVIEW",
    "APPROVED",
    "REJECTED",
    "FAILED",
]


class AgentState(TypedDict, total=False):
    tenant_id: int
    receipt_id: int
    file_path: str
    file_hash: str
    attempt_number: int
    transaction_date: date | None
    law_as_of_date: date | None
    law_corpus_version: str
    image_quality: str | None
    image_quality_result: dict[str, object] | None
    parsed_receipt: dict[str, Any] | None
    retrieval_query: str | None
    relevant_laws: list[dict[str, Any]]
    calculation_result: dict[str, Any] | None
    draft_decision: dict[str, Any] | None
    final_decision: dict[str, Any] | None
    requires_human: bool
    error_message: str | None
    status: WorkflowStatus
    saved: bool
