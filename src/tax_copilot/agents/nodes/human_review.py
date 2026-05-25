"""HITL 인터럽트 노드.

핵심 원칙 (위반 시 심각한 버그):
- 이 노드에서 LLM 호출 금지
- 이 노드에서 DB 저장 금지
- 이 노드에서 외부 API 호출 금지
- 이유: resume 시 interrupt() 이후 코드부터 재실행되는데,
  interrupt() 전 코드가 있으면 resume 때 다시 실행되어 중복 처리가 발생한다.

흐름:
1. audit_prepare_node가 draft_decision을 state에 저장
2. 이 노드는 그 draft_decision을 세무사에게 보여주고 interrupt()
3. 세무사가 Command(resume={"approved": True/False, "comment": "..."}) 전송
4. resume 이후 세무사 결정을 final_decision에 합침
5. save_result_node에서 DB 저장
"""

from langgraph.types import interrupt

from tax_copilot.agents.state import AgentState


async def human_review_node(state: AgentState) -> dict:
    """세무사 검토를 기다린다. interrupt() 이후 코드는 resume 시 실행된다."""
    # interrupt()에 세무사에게 보여줄 정보를 전달
    human_decision: dict = interrupt(
        {
            "type": "TAX_REVIEW_REQUIRED",
            "receipt_id": state["receipt_id"],
            "parsed_receipt": state.get("parsed_receipt"),
            "draft_decision": state.get("draft_decision"),
            "relevant_laws": state.get("relevant_laws", []),
        }
    )

    # 이 아래는 resume 시 실행됨
    draft = state.get("draft_decision") or {}
    final_decision = {
        **draft,
        "human_approved": human_decision.get("approved"),
        "human_comment": human_decision.get("comment"),
        "requires_human_review": False,  # 검토 완료
    }

    return {"final_decision": final_decision}
