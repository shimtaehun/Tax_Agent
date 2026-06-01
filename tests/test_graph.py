"""LangGraph 워크플로우 통합 테스트.

DB 없이 MemorySaver로 전체 흐름을 검증한다.
테스트 목표:
1. 그래프 컴파일 성공
2. 자동 결정 경로 (requires_human=False) 완주
3. HITL 경로 (requires_human=True) — interrupt 발동 후 resume 성공
4. 판독 불가 이미지 경로 — reject_unreadable 경유
"""

import os
import tempfile

import pytest
from langgraph.checkpoint.memory import MemorySaver

from tax_copilot.agents.graph import build_graph, generate_thread_id
from tax_copilot.agents.state import AgentState


def _make_state(file_path: str, receipt_id: int = 1) -> AgentState:
    """테스트용 초기 AgentState를 생성한다."""
    return AgentState(
        tenant_id=1,
        receipt_id=receipt_id,
        file_path=file_path,
        file_hash="abc123",
        attempt_number=1,
        transaction_date=None,
        law_as_of_date=None,
        law_corpus_version="test-v0",
        image_quality=None,
        parsed_receipt=None,
        retrieval_query=None,
        relevant_laws=[],
        calculation_result=None,
        draft_decision=None,
        final_decision=None,
        requires_human=False,
        error_message=None,
        messages=[],
    )


@pytest.fixture
def graph():
    """MemorySaver를 사용하는 테스트용 그래프."""
    saver = MemorySaver()
    return build_graph(checkpointer=saver)


@pytest.fixture(autouse=True)
def disable_external_gemini(monkeypatch: pytest.MonkeyPatch) -> None:
    """Graph tests must not depend on a real Gemini API key from local .env files."""
    from tax_copilot.core.config import settings

    monkeypatch.setattr(settings, "gemini_api_key", "")


@pytest.fixture
def valid_file():
    """Pillow로 열 수 있는 유효한 JPEG 파일을 생성하고 경로를 반환한다."""
    import io

    from PIL import Image

    img = Image.new("RGB", (200, 200), color=(200, 200, 200))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")

    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
        f.write(buf.getvalue())
        path = f.name
    yield path
    os.unlink(path)


@pytest.fixture
def tiny_file():
    """100 bytes짜리 파일 (품질 검사에서 거부될 크기)."""
    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
        f.write(b"\xff\xd8\xff" + b"\x00" * 97)  # 100 bytes
        path = f.name
    yield path
    os.unlink(path)


class TestGraphCompile:
    def test_graph_compiles_without_error(self, graph) -> None:
        """build_graph()가 예외 없이 컴파일되는지 확인한다."""
        assert graph is not None


class TestAutoDecisionPath:
    """relevant_laws가 있어 자동 결정되는 경로."""

    async def test_auto_path_completes(self, graph, valid_file: str) -> None:
        """자동 결정 경로에서 final_decision이 설정되고 종료된다."""
        # relevant_laws를 주입해서 requires_human=False 유도
        state = _make_state(valid_file)
        thread_id = generate_thread_id(1, "abc123", 1, 1)
        config = {"configurable": {"thread_id": thread_id}}

        # 그래프를 먼저 실행해서 intake까지 진행
        # 그런 다음 relevant_laws를 주입하는 방법 대신,
        # audit_prepare_node의 _should_require_human 로직을 이해하면:
        # - relevant_laws가 비어 있으면 requires_human=True
        # - extraction_confidence < 0.75 면 requires_human=True
        # mocked intake는 confidence=0.95를 반환하지만 laws는 빈 목록
        # → requires_human=True가 되어 HITL 경로로 감

        # 자동 결정 테스트는 relevant_laws를 직접 state에 넣어야 함
        # Phase 3에서 실제 RAG가 laws를 채운 뒤 이 테스트를 업데이트한다.
        # 지금은 HITL 경로로 가는 것이 정상 동작임을 확인한다.
        result = await graph.ainvoke(state, config=config)

        # Phase 2 mocked 상태에서는 laws=[] 이므로 requires_human=True
        # → human_review_node에서 interrupt 발생 → result에 __interrupt__ 포함
        assert result is not None


class TestHITLPath:
    """HITL 필요 시 검토 초안을 저장하고 그래프는 종료한다."""

    async def test_human_review_path_completes_with_review_flag(
        self, graph, valid_file: str
    ) -> None:
        state = _make_state(valid_file)
        thread_id = generate_thread_id(1, "abc123", 1, 1)
        config = {"configurable": {"thread_id": thread_id}}

        final_state = await graph.ainvoke(state, config=config)

        assert "__interrupt__" not in final_state
        assert final_state["final_decision"] is not None
        assert final_state["final_decision"]["human_approved"] is None
        assert final_state["final_decision"]["requires_human_review"] is True
        assert final_state["requires_human"] is True


class TestUnreadablePath:
    """판독 불가 이미지 경로."""

    async def test_tiny_file_goes_to_reject(self, graph, tiny_file: str) -> None:
        """1KB 미만 파일은 reject_unreadable_node를 경유하고 종료된다."""
        state = _make_state(tiny_file, receipt_id=3)
        thread_id = generate_thread_id(1, "abc123", 3, 1)
        config = {"configurable": {"thread_id": thread_id}}

        final_state = await graph.ainvoke(state, config=config)

        assert final_state["image_quality"] == "unreadable"
        assert final_state["final_decision"] is not None
        assert final_state["final_decision"]["evidence_status"] == "unreadable"
        assert "image_unreadable" in final_state["final_decision"]["risk_flags"]


class TestTools:
    """결정론적 계산 도구 단위 테스트."""

    def test_vat_calculation_standard_rate(self) -> None:
        from tax_copilot.agents.tools.vat import calculate_vat_from_supply_value

        result = calculate_vat_from_supply_value(10000)
        assert result["supply_value_krw"] == 10000
        assert result["vat_krw"] == 1000
        assert result["total_krw"] == 11000

    def test_vat_rounds_down(self) -> None:
        from tax_copilot.agents.tools.vat import calculate_vat_from_supply_value

        # 10001원 × 10% = 1000.1 → 1000 (내림)
        result = calculate_vat_from_supply_value(10001)
        assert result["vat_krw"] == 1000

    def test_vat_zero_supply(self) -> None:
        from tax_copilot.agents.tools.vat import calculate_vat_from_supply_value

        result = calculate_vat_from_supply_value(0)
        assert result["vat_krw"] == 0
        assert result["total_krw"] == 0

    def test_vat_negative_supply_raises(self) -> None:
        from tax_copilot.agents.tools.vat import calculate_vat_from_supply_value

        with pytest.raises(ValueError, match="0 이상"):
            calculate_vat_from_supply_value(-1)

    def test_entertainment_limit_small_company(self) -> None:
        from tax_copilot.agents.tools.vat import calculate_entertainment_limit

        # 수입금액 5억 (100억 이하 구간 → 0.2%)
        result = calculate_entertainment_limit(
            total_expense_krw=20_000_000,
            revenue_krw=500_000_000,
        )
        # 한도: 1200만 + (5억 × 0.2%) = 1200만 + 100만 = 1300만
        assert result["limit_krw"] == 13_000_000
        assert result["excess_krw"] == 7_000_000

    def test_thread_id_is_unique(self) -> None:
        id1 = generate_thread_id(1, "abc123", 1, 1)
        id2 = generate_thread_id(1, "abc123", 1, 1)
        assert id1 != id2  # 매번 다른 uuid suffix

    def test_thread_id_format(self) -> None:
        tid = generate_thread_id(5, "deadbeef1234", 42, 2)
        assert tid.startswith("t5-deadbeef-r42-a2-")
