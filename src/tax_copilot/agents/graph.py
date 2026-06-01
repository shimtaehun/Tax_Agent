"""LangGraph 워크플로우 그래프.

구조:
  START → image_quality
    → (unreadable) → reject_unreadable → save_result → END
    → (ok)         → intake → duplicate_check → build_retrieval_query → tax_law_retrieval
                            → calculation → audit_prepare → save_result → END

핵심 설계 규칙:
- audit_prepare_node: 판단 초안과 HITL 필요 여부를 state에 저장
- save_result_node: 자동 승인 또는 검토 대기 초안을 final_decision으로 승격
- 세무사 승인/반려 결정은 reviews API가 DB에 저장된 초안에 병합
"""

from uuid import uuid4

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from tax_copilot.agents.nodes.audit_prepare import audit_prepare_node
from tax_copilot.agents.nodes.calculation import calculation_node
from tax_copilot.agents.nodes.duplicate_check import duplicate_check_node
from tax_copilot.agents.nodes.image_quality import image_quality_node
from tax_copilot.agents.nodes.intake import intake_node
from tax_copilot.agents.nodes.retrieval import build_retrieval_query_node, tax_law_retrieval_node
from tax_copilot.agents.nodes.save_result import reject_unreadable_node, save_result_node
from tax_copilot.agents.state import AgentState


async def _route_after_quality(state: AgentState) -> str:
    """이미지 품질에 따라 처리 경로를 결정한다."""
    return "reject_unreadable" if state.get("image_quality") == "unreadable" else "intake"


def build_graph(checkpointer: BaseCheckpointSaver) -> CompiledStateGraph:
    """그래프를 빌드하고 컴파일한다."""
    builder = StateGraph(AgentState)

    # 노드 등록
    builder.add_node("image_quality", image_quality_node)
    builder.add_node("reject_unreadable", reject_unreadable_node)
    builder.add_node("intake", intake_node)
    builder.add_node("duplicate_check", duplicate_check_node)
    builder.add_node("build_retrieval_query", build_retrieval_query_node)
    builder.add_node("tax_law_retrieval", tax_law_retrieval_node)
    builder.add_node("calculation", calculation_node)
    builder.add_node("audit_prepare", audit_prepare_node)
    builder.add_node("save_result", save_result_node)

    # 엣지 연결
    builder.add_edge(START, "image_quality")
    builder.add_conditional_edges(
        "image_quality",
        _route_after_quality,
        {"reject_unreadable": "reject_unreadable", "intake": "intake"},
    )
    builder.add_edge("reject_unreadable", "save_result")
    builder.add_edge("intake", "duplicate_check")
    builder.add_edge("duplicate_check", "build_retrieval_query")
    builder.add_edge("build_retrieval_query", "tax_law_retrieval")
    builder.add_edge("tax_law_retrieval", "calculation")
    builder.add_edge("calculation", "audit_prepare")
    builder.add_edge("audit_prepare", "save_result")
    builder.add_edge("save_result", END)

    return builder.compile(checkpointer=checkpointer)


def generate_thread_id(tenant_id: int, file_hash: str, receipt_id: int, attempt_number: int) -> str:
    """고유 thread_id를 생성한다.

    재처리 시 새로운 suffix를 붙여 이전 checkpoint에서 잘못 재개되는 것을 방지한다.
    """
    suffix = uuid4().hex[:8]
    return f"t{tenant_id}-{file_hash[:8]}-r{receipt_id}-a{attempt_number}-{suffix}"
