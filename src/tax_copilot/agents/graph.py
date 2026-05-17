from typing import Any

from tax_copilot.core.workflows.nodes import (
    audit_prepare_node,
    build_retrieval_query_node,
    calculation_node,
    image_quality_node,
    mock_intake_node,
    mock_law_retrieval_node,
    reject_unreadable_node,
    save_result_node,
)
from tax_copilot.core.workflows.state import AgentState


def _route_after_audit(state: AgentState) -> str:
    return "human_review" if state.get("requires_human") else "save_result"


def _route_after_quality(state: AgentState) -> str:
    return "intake" if state.get("image_quality") == "readable" else "reject_unreadable"


def build_graph(checkpointer: Any | None = None) -> Any:
    try:
        from langgraph.graph import END, START, StateGraph
        from langgraph.types import interrupt
    except ModuleNotFoundError as e:
        raise RuntimeError("langgraph is not installed. Run pip-sync requirements/dev.txt.") from e

    def human_review_node(state: AgentState) -> dict[str, Any]:
        human_decision = interrupt(
            {
                "type": "TAX_REVIEW_REQUIRED",
                "receipt_id": state["receipt_id"],
                "parsed_receipt": state.get("parsed_receipt"),
                "draft_decision": state.get("draft_decision"),
                "relevant_laws": state.get("relevant_laws", []),
            }
        )
        draft = dict(state["draft_decision"] or {})
        approved = bool(human_decision.get("approved"))
        draft["human_decision"] = approved
        draft["human_comment"] = human_decision.get("comment")
        draft["requires_human_review"] = False
        return {
            "final_decision": draft,
            "requires_human": False,
            "status": "APPROVED" if approved else "REJECTED",
        }

    graph = StateGraph(AgentState)
    graph.add_node("image_quality", image_quality_node)
    graph.add_node("reject_unreadable", reject_unreadable_node)
    graph.add_node("intake", mock_intake_node)
    graph.add_node("build_retrieval_query", build_retrieval_query_node)
    graph.add_node("tax_law_retrieval", mock_law_retrieval_node)
    graph.add_node("calculation", calculation_node)
    graph.add_node("audit_prepare", audit_prepare_node)
    graph.add_node("human_review", human_review_node)
    graph.add_node("save_result", save_result_node)

    graph.add_edge(START, "image_quality")
    graph.add_conditional_edges(
        "image_quality",
        _route_after_quality,
        {"intake": "intake", "reject_unreadable": "reject_unreadable"},
    )
    graph.add_edge("reject_unreadable", "human_review")
    graph.add_edge("intake", "build_retrieval_query")
    graph.add_edge("build_retrieval_query", "tax_law_retrieval")
    graph.add_edge("tax_law_retrieval", "calculation")
    graph.add_edge("calculation", "audit_prepare")
    graph.add_conditional_edges(
        "audit_prepare",
        _route_after_audit,
        {"human_review": "human_review", "save_result": "save_result"},
    )
    graph.add_edge("human_review", "save_result")
    graph.add_edge("save_result", END)
    return graph.compile(checkpointer=checkpointer)
