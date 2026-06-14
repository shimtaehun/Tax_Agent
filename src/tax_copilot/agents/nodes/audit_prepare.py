"""판단 초안 생성 노드.

핵심 원칙:
- 이 노드에서 LLM 판단 초안을 만들고 state에 저장한다.
- interrupt()는 절대 이 노드에서 호출하지 않는다.
- interrupt()는 human_review_node에서만 호출한다.
- 이유: resume 시 이 노드가 재실행되면 LLM 비용이 이중 발생하고 결과가 달라질 수 있다.
"""

from tax_copilot.agents.state import AgentState
from tax_copilot.core.tax.account_classifier import classify_account_code

_NO_EXPIRY = 99991231


def _int_to_date_str(val: int | None) -> str | None:
    """YYYYMMDD 정수를 'YYYY-MM-DD' 문자열로 변환. None이거나 NO_EXPIRY면 None 반환."""
    if val is None or val == _NO_EXPIRY:
        return None
    s = str(val)
    return f"{s[:4]}-{s[4:6]}-{s[6:]}"


_PROMPT_VERSION = "v0.3-rule-based"
_MODEL_NAME = "rule-based"

# 증빙 종류별 부가세 공제 가능 여부
_VAT_CREDITABLE_BY_EVIDENCE: dict[str, bool | None] = {
    "tax_invoice": True,
    "credit_card_slip": True,
    "cash_receipt": True,
    "invoice": False,
    "simplified_receipt": False,
    "unknown": None,
}


def _should_require_human(state: AgentState) -> tuple[bool, str | None]:
    parsed = state.get("parsed_receipt") or {}

    if not state.get("relevant_laws"):
        return True, "검색된 법령 근거가 없습니다."

    confidence = parsed.get("extraction_confidence", 0.0)
    if confidence < 0.75:
        return True, f"추출 신뢰도가 낮습니다: {confidence:.2f}"

    if state.get("calculation_result") is None and parsed.get("supply_value_krw") is not None:
        return True, "세액 계산에 실패했습니다."

    if parsed.get("evidence_type", "unknown") == "unknown":
        return True, "증빙 종류를 판별할 수 없습니다."

    return False, None


def _build_risk_flags(parsed: dict) -> list[str]:
    flags: list[str] = []
    evidence_type = parsed.get("evidence_type", "unknown")
    total = parsed.get("total_amount_krw") or 0

    if evidence_type == "simplified_receipt" and total > 30000:
        flags.append("simplified_receipt_over_30k")

    if not parsed.get("transaction_date"):
        flags.append("missing_transaction_date")

    if evidence_type == "tax_invoice" and not parsed.get("merchant_business_no"):
        flags.append("missing_business_no_on_tax_invoice")

    return flags


async def audit_prepare_node(state: AgentState) -> dict:
    """판단 초안을 생성하고 HITL 필요 여부를 결정한다."""
    parsed = state.get("parsed_receipt") or {}
    calc = state.get("calculation_result")
    laws = state.get("relevant_laws", [])
    evidence_type = parsed.get("evidence_type", "unknown")
    merchant_name = parsed.get("merchant_name")

    requires_human, review_reason = _should_require_human(state)
    risk_flags = _build_risk_flags(parsed)

    if risk_flags and not requires_human:
        requires_human = True
        review_reason = f"위험 플래그 발견: {', '.join(risk_flags)}"

    vat_creditable = None if requires_human else _VAT_CREDITABLE_BY_EVIDENCE.get(evidence_type)
    account_code, account_code_reason = classify_account_code(merchant_name, evidence_type)

    draft = {
        "vat_creditable": vat_creditable,
        "expense_deductible": None if requires_human else True,
        "account_code": account_code,
        "account_code_reason": account_code_reason,
        "evidence_type": evidence_type,
        "evidence_status": "valid" if parsed.get("merchant_name") else "unknown",
        "confidence": parsed.get("extraction_confidence", 0.0),
        "risk_flags": risk_flags,
        "citations": [
            {
                "chunk_id": law.get("chunk_id"),
                "law_name": law.get("law_name"),
                "article_no": law.get("article_no"),
                "paragraph_no": law.get("paragraph_no"),
                "effective_from": _int_to_date_str(law.get("effective_from_int")),
                "effective_to": _int_to_date_str(law.get("effective_to_int")),
                "quoted_text": law.get("content", ""),
            }
            for law in laws
        ],
        "requires_human_review": requires_human,
        "review_reason": review_reason,
        "prompt_version": _PROMPT_VERSION,
        "model_name": _MODEL_NAME,
        "law_corpus_version": state.get("law_corpus_version", "unknown"),
        "calculation_result": calc,
    }

    return {
        "draft_decision": draft,
        "requires_human": requires_human,
    }
