import importlib.util

import pytest

from tax_copilot.agents import build_graph
from tax_copilot.core.schemas import ParsedReceipt
from tax_copilot.core.tax import calculate_vat_amounts
from tax_copilot.core.workflows.nodes import resume_after_review, run_until_interrupt
from tax_copilot.core.workflows.threading import generate_thread_id


def test_deterministic_vat_calculation_from_total() -> None:
    result = calculate_vat_amounts(ParsedReceipt(total_amount_krw=11000))

    assert result.supply_value_krw == 10000
    assert result.vat_amount_krw == 1000


def test_mock_workflow_interrupt_and_resume() -> None:
    interrupted = run_until_interrupt(
        {
            "tenant_id": 1,
            "receipt_id": 10,
            "file_path": "local://receipt.jpg",
            "file_hash": "a" * 64,
            "attempt_number": 1,
            "status": "PENDING",
        }
    )

    assert interrupted["status"] == "AWAITING_REVIEW"
    assert interrupted["requires_human"] is True
    draft_decision = interrupted["draft_decision"]
    calculation_result = interrupted["calculation_result"]
    assert draft_decision is not None
    assert calculation_result is not None
    assert draft_decision["requires_human_review"] is True
    assert calculation_result["vat_amount_krw"] == 1000
    assert interrupted["relevant_laws"]
    assert interrupted["relevant_laws"][0]["chunk_id"].startswith(("vat-", "cit-"))

    resumed = resume_after_review(interrupted, {"approved": True, "comment": "검토 승인"})

    assert resumed["status"] == "APPROVED"
    assert resumed["saved"] is True
    final_decision = resumed["final_decision"]
    assert final_decision is not None
    assert final_decision["human_decision"] is True
    assert final_decision["requires_human_review"] is False


def test_workflow_routes_unreadable_image_to_human_review() -> None:
    interrupted = run_until_interrupt(
        {
            "tenant_id": 1,
            "receipt_id": 11,
            "file_path": "local://bad-receipt.jpg",
            "file_hash": "b" * 64,
            "attempt_number": 1,
            "status": "PENDING",
            "image_quality_result": {
                "status": "unreadable",
                "reason": "image_too_small",
                "dimensions": {"width": 320, "height": 180},
                "file_size_bytes": 256,
            },
        }
    )

    assert interrupted["status"] == "AWAITING_REVIEW"
    assert interrupted["image_quality"] == "unreadable"
    assert interrupted["requires_human"] is True
    assert interrupted["draft_decision"] is not None
    assert interrupted["draft_decision"]["evidence_status"] == "unreadable"


def test_thread_id_contains_attempt_number_and_unique_suffix() -> None:
    first = generate_thread_id(1, "abcdef123456", 7, 1)
    second = generate_thread_id(1, "abcdef123456", 7, 2)

    assert first.startswith("t1-abcdef12-r7-a1-")
    assert second.startswith("t1-abcdef12-r7-a2-")
    assert first != second


@pytest.mark.skipif(importlib.util.find_spec("langgraph") is None, reason="langgraph not installed")
def test_langgraph_compile() -> None:
    graph = build_graph()

    assert graph is not None


@pytest.mark.skipif(importlib.util.find_spec("langgraph") is None, reason="langgraph not installed")
def test_langgraph_interrupt_and_resume() -> None:
    from langgraph.checkpoint.memory import InMemorySaver
    from langgraph.types import Command

    graph = build_graph(checkpointer=InMemorySaver())
    config = {"configurable": {"thread_id": "phase2-test-thread"}}
    first = graph.invoke(
        {
            "tenant_id": 1,
            "receipt_id": 10,
            "file_path": "local://receipt.jpg",
            "file_hash": "a" * 64,
            "attempt_number": 1,
            "status": "PENDING",
        },
        config=config,
    )

    assert first["status"] == "AWAITING_REVIEW"
    assert "__interrupt__" in first

    resumed = graph.invoke(
        Command(resume={"approved": True, "comment": "검토 승인"}),
        config=config,
    )

    assert resumed["status"] == "APPROVED"
    assert resumed["saved"] is True
    assert resumed["final_decision"]["human_decision"] is True


@pytest.mark.skipif(importlib.util.find_spec("langgraph") is None, reason="langgraph not installed")
def test_langgraph_unreadable_image_interrupt_and_resume() -> None:
    from langgraph.checkpoint.memory import InMemorySaver
    from langgraph.types import Command

    graph = build_graph(checkpointer=InMemorySaver())
    config = {"configurable": {"thread_id": "phase4-unreadable-test-thread"}}
    first = graph.invoke(
        {
            "tenant_id": 1,
            "receipt_id": 11,
            "file_path": "local://bad-receipt.jpg",
            "file_hash": "b" * 64,
            "attempt_number": 1,
            "status": "PENDING",
            "image_quality_result": {
                "status": "unreadable",
                "reason": "image_too_small",
                "dimensions": {"width": 320, "height": 180},
                "file_size_bytes": 256,
            },
        },
        config=config,
    )

    assert first["status"] == "AWAITING_REVIEW"
    assert first["draft_decision"]["evidence_status"] == "unreadable"
    assert "__interrupt__" in first

    resumed = graph.invoke(
        Command(resume={"approved": False, "comment": "재업로드 필요"}),
        config=config,
    )

    assert resumed["status"] == "REJECTED"
    assert resumed["saved"] is True
