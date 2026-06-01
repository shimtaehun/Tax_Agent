"""결과 저장 노드.

자동 판단과 HITL 두 경로 모두의 마지막 노드.
Phase 2: state에 완료 플래그만 설정 (DB 저장은 Celery task가 담당).
Phase 5에서 Celery task가 이 노드 완료 후 receipts 테이블을 업데이트한다.
"""

from tax_copilot.agents.state import AgentState


async def save_result_node(state: AgentState) -> dict:
    """워크플로우 완료를 표시한다.

    자동 승인 경로: draft_decision → final_decision으로 복사.
    HITL 경로: human_review_node가 이미 final_decision을 설정한 상태.
    """
    if state.get("final_decision") is None:
        # 자동 결정 경로 — draft를 final로 승격
        draft = state.get("draft_decision") or {}
        requires_human = state.get("requires_human", False)
        return {
            "final_decision": {
                **draft,
                "human_approved": None,
                "human_comment": None,
                "requires_human_review": requires_human,
            }
        }

    # HITL 경로 — final_decision이 이미 설정됨
    return {}


async def reject_unreadable_node(state: AgentState) -> dict:
    """판독 불가 이미지를 처리한다."""
    return {
        "final_decision": {
            "vat_creditable": None,
            "expense_deductible": None,
            "account_code": "미분류",
            "account_code_reason": None,
            "evidence_type": "unknown",
            "evidence_status": "unreadable",
            "confidence": 0.0,
            "risk_flags": ["image_unreadable"],
            "citations": [],
            "requires_human_review": True,
            "review_reason": state.get("error_message") or "이미지를 판독할 수 없습니다.",
            "human_approved": None,
            "human_comment": None,
        },
        "requires_human": True,
    }
