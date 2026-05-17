from datetime import date
from typing import Any, cast

from tax_copilot.core.rag import DEFAULT_TAX_LAW_CORPUS, search_tax_law
from tax_copilot.core.schemas import Citation, ParsedReceipt, TaxDecision
from tax_copilot.core.tax import calculate_vat_amounts
from tax_copilot.core.workflows.state import AgentState

MOCK_CORPUS_VERSION = "mock-tax-law-2026.1"
PROMPT_VERSION = "mock-audit-v1"
MODEL_NAME = "mock-deterministic"


def image_quality_node(state: AgentState) -> dict[str, str]:
    quality = state.get("image_quality_result")
    if quality and quality.get("status") != "readable":
        return {"image_quality": str(quality["status"]), "status": "AWAITING_REVIEW"}
    return {"image_quality": "readable", "status": "PROCESSING"}


def reject_unreadable_node(state: AgentState) -> dict[str, Any]:
    quality = state.get("image_quality_result") or {}
    reason = str(quality.get("reason") or "receipt_image_unreadable")
    decision = TaxDecision(
        vat_creditable=None,
        expense_deductible=None,
        account_title=None,
        evidence_type="unknown",
        evidence_status="unreadable",
        confidence=0.0,
        risk_flags=["image_quality_failed", reason],
        citations=[],
        requires_human_review=True,
        review_reason=f"Receipt image quality failed: {reason}",
        prompt_version=PROMPT_VERSION,
        model_name=MODEL_NAME,
        law_corpus_version=MOCK_CORPUS_VERSION,
    )
    return {
        "parsed_receipt": ParsedReceipt(evidence_type="unknown").model_dump(mode="json"),
        "relevant_laws": [],
        "calculation_result": {
            "total_amount_krw": 0,
            "supply_value_krw": 0,
            "vat_amount_krw": 0,
            "vat_rate_basis_points": 1000,
        },
        "draft_decision": decision.model_dump(mode="json"),
        "requires_human": True,
        "status": "AWAITING_REVIEW",
        "error_message": reason,
    }


def mock_intake_node(state: AgentState) -> dict[str, Any]:
    parsed = ParsedReceipt.model_validate(
        state.get("parsed_receipt")
        or {
            "merchant_name": "Mock Merchant",
            "transaction_date": "2026-01-15",
            "total_amount_krw": 11000,
            "evidence_type": "credit_card_slip",
            "payment_method": "card",
        }
    )
    return {
        "parsed_receipt": parsed.model_dump(mode="json"),
        "transaction_date": parsed.transaction_date,
        "law_as_of_date": parsed.transaction_date,
    }


def build_retrieval_query_node(state: AgentState) -> dict[str, str]:
    parsed = ParsedReceipt.model_validate(state["parsed_receipt"])
    evidence = parsed.evidence_type
    merchant = parsed.merchant_name or "unknown merchant"
    return {"retrieval_query": f"VAT input tax credit {evidence} {merchant}"}


def mock_law_retrieval_node(state: AgentState) -> dict[str, Any]:
    as_of_date = state.get("law_as_of_date") or state.get("transaction_date") or date(2026, 1, 1)
    query = state.get("retrieval_query") or "VAT input tax credit evidence business expense"
    search_results = search_tax_law(query, as_of_date, top_k=3)
    citations = [
        Citation(
            chunk_id=result.chunk.chunk_id,
            law_name=result.chunk.law_name,
            article_no=result.chunk.article_no,
            paragraph_no=result.chunk.paragraph_no,
            effective_from=result.chunk.effective_from,
            effective_to=result.chunk.effective_to,
            quoted_text=result.chunk.content,
        )
        for result in search_results
    ]
    return {
        "relevant_laws": [citation.model_dump(mode="json") for citation in citations],
        "law_corpus_version": DEFAULT_TAX_LAW_CORPUS[0].corpus_version,
    }


def calculation_node(state: AgentState) -> dict[str, dict[str, Any]]:
    parsed = ParsedReceipt.model_validate(state["parsed_receipt"])
    calculation = calculate_vat_amounts(parsed)
    return {"calculation_result": calculation.model_dump()}


def audit_prepare_node(state: AgentState) -> dict[str, Any]:
    parsed = ParsedReceipt.model_validate(state["parsed_receipt"])
    calculation = state["calculation_result"] or {}
    citations = [Citation.model_validate(item) for item in state.get("relevant_laws", [])]
    decision = TaxDecision(
        vat_creditable=None,
        expense_deductible=None,
        account_title="미확정",
        evidence_type=parsed.evidence_type,
        evidence_status="valid" if parsed.evidence_type != "unknown" else "unknown",
        confidence=0.62,
        risk_flags=["human_review_required", "business_purpose_unverified"],
        citations=citations,
        requires_human_review=True,
        review_reason="Business purpose and final tax treatment require professional review.",
        prompt_version=PROMPT_VERSION,
        model_name=MODEL_NAME,
        law_corpus_version=state.get("law_corpus_version", MOCK_CORPUS_VERSION),
    )
    draft = decision.model_dump(mode="json")
    draft["calculation"] = calculation
    return {"draft_decision": draft, "requires_human": True, "status": "AWAITING_REVIEW"}


def apply_human_review_node(state: AgentState, resume: dict[str, Any]) -> dict[str, Any]:
    draft = dict(state["draft_decision"] or {})
    approved = bool(resume.get("approved"))
    draft["human_decision"] = approved
    draft["human_comment"] = resume.get("comment")
    draft["requires_human_review"] = False
    return {
        "final_decision": draft,
        "requires_human": False,
        "status": "APPROVED" if approved else "REJECTED",
    }


def save_result_node(state: AgentState) -> dict[str, bool]:
    return {"saved": True}


def run_until_interrupt(initial_state: AgentState) -> AgentState:
    state: dict[str, Any] = dict(initial_state)
    state.update(image_quality_node(cast(AgentState, state)))
    if state.get("image_quality") != "readable":
        state.update(reject_unreadable_node(cast(AgentState, state)))
        return cast(AgentState, state)

    for node in (
        mock_intake_node,
        build_retrieval_query_node,
        mock_law_retrieval_node,
        calculation_node,
        audit_prepare_node,
    ):
        state.update(node(cast(AgentState, state)))
    return cast(AgentState, state)


def resume_after_review(state: AgentState, resume: dict[str, Any]) -> AgentState:
    next_state: dict[str, Any] = dict(state)
    state_for_nodes = cast(AgentState, next_state)
    next_state.update(apply_human_review_node(state_for_nodes, resume))
    next_state.update(save_result_node(cast(AgentState, next_state)))
    return cast(AgentState, next_state)
