"""RAG 파이프라인 테스트.

Gemini API 없이 mock 벡터를 사용하여 테스트한다.
거래일 기준 필터 동작을 중심으로 검증한다.
"""

import hashlib
from datetime import date
from unittest.mock import AsyncMock, patch

import pytest

from tax_copilot.core.rag.schemas import LawChunk
from tax_copilot.infra.vector.qdrant import (
    EMBEDDING_DIM,
    ensure_collection,
    get_client,
    reset_client,
    search_by_date,
    upsert_chunks,
)

_CORPUS_VERSION = "test-v1"


def _make_chunk(
    chunk_id: str,
    content: str,
    effective_from: date,
    effective_to: date | None = None,
    is_current: bool = True,
) -> LawChunk:
    return LawChunk(
        chunk_id=chunk_id,
        law_id="vat",
        law_name="부가가치세법",
        article_no="제38조",
        content=content,
        effective_from=effective_from,
        effective_to=effective_to,
        is_current=is_current,
        content_hash=hashlib.sha256(content.encode()).hexdigest(),
        corpus_version=_CORPUS_VERSION,
    )


def _dummy_vector(seed: int = 0) -> list[float]:
    """테스트용 더미 벡터 (운영 임베딩 차원, 정규화)."""
    import math

    v = [float(i + seed) for i in range(EMBEDDING_DIM)]
    norm = math.sqrt(sum(x * x for x in v))
    return [x / norm for x in v]


@pytest.fixture(autouse=True)
def fresh_client():
    """각 테스트마다 in-memory Qdrant 클라이언트를 초기화한다."""
    reset_client()
    client = get_client(in_memory=True)
    ensure_collection(client)
    yield client
    reset_client()


class TestLawChunkSchema:
    def test_is_valid_as_of_current(self) -> None:
        """is_current=True인 chunk는 어떤 날짜든 유효하다."""
        chunk = _make_chunk("c1", "내용", date(2014, 1, 1), is_current=True)
        assert chunk.is_valid_as_of(date(2024, 6, 15)) is True

    def test_is_valid_as_of_before_effective(self) -> None:
        """effective_from 이전 날짜는 유효하지 않다."""
        chunk = _make_chunk("c2", "내용", date(2024, 1, 1), is_current=True)
        assert chunk.is_valid_as_of(date(2023, 12, 31)) is False

    def test_is_valid_as_of_after_effective_to(self) -> None:
        """effective_to 이후 날짜는 유효하지 않다."""
        chunk = _make_chunk(
            "c3", "내용", date(2014, 1, 1), effective_to=date(2020, 1, 1), is_current=False
        )  # noqa: E501
        assert chunk.is_valid_as_of(date(2020, 1, 1)) is False

    def test_is_valid_as_of_within_range(self) -> None:
        """effective_from <= as_of_date < effective_to 구간은 유효하다."""
        chunk = _make_chunk(
            "c4", "내용", date(2014, 1, 1), effective_to=date(2025, 1, 1), is_current=False
        )  # noqa: E501
        assert chunk.is_valid_as_of(date(2024, 6, 15)) is True


class TestQdrantUpsertAndSearch:
    def test_upsert_and_search_returns_results(self, fresh_client) -> None:
        """upsert 후 검색하면 결과가 반환된다."""
        chunk = _make_chunk("vat-art38-p1-test01", "매입세액 공제 신용카드", date(2014, 1, 1))
        vector = _dummy_vector(0)
        upsert_chunks(fresh_client, [chunk], [vector])

        results = search_by_date(fresh_client, vector, date(2024, 6, 15))
        assert len(results) == 1
        assert results[0]["chunk_id"] == "vat-art38-p1-test01"
        assert results[0]["law_name"] == "부가가치세법"
        assert "score" in results[0]

    def test_date_filter_excludes_future_laws(self, fresh_client) -> None:
        """거래일 이후에 시행된 법령은 검색되지 않는다."""
        chunk = _make_chunk(
            "vat-art38-future-01",
            "미래 법령 내용",
            effective_from=date(2025, 1, 1),  # 2025년 시행
            is_current=True,
        )
        vector = _dummy_vector(0)
        upsert_chunks(fresh_client, [chunk], [vector])

        # 거래일 2024-06-15: 이 법령은 아직 시행 전
        results = search_by_date(fresh_client, vector, date(2024, 6, 15))
        assert len(results) == 0

    def test_date_filter_includes_current_law(self, fresh_client) -> None:
        """현행법(effective_to=None, is_current=True)은 과거 거래일에도 검색된다."""
        chunk = _make_chunk(
            "vat-art38-current-01",
            "현행 법령 매입세액",
            effective_from=date(2014, 1, 1),
            is_current=True,
        )
        vector = _dummy_vector(0)
        upsert_chunks(fresh_client, [chunk], [vector])

        results = search_by_date(fresh_client, vector, date(2020, 6, 15))
        assert len(results) == 1

    def test_date_filter_excludes_expired_law(self, fresh_client) -> None:
        """개정으로 폐지된 구 법령은 effective_to 이후 거래일에는 검색되지 않는다."""
        chunk = _make_chunk(
            "vat-art38-old-01",
            "구 법령 내용",
            effective_from=date(2014, 1, 1),
            effective_to=date(2020, 1, 1),  # 2020년에 개정
            is_current=False,
        )
        vector = _dummy_vector(0)
        upsert_chunks(fresh_client, [chunk], [vector])

        # 2020년 이후 거래 → 구 법령은 해당 없음
        results = search_by_date(fresh_client, vector, date(2021, 3, 15))
        assert len(results) == 0

        # 2020년 이전 거래 → 구 법령이 유효
        results = search_by_date(fresh_client, vector, date(2019, 6, 15))
        assert len(results) == 1

    def test_search_top_k_limit(self, fresh_client) -> None:
        """top_k로 반환 개수를 제한한다."""
        chunks = [
            _make_chunk(f"vat-art38-{i:02d}", f"법령 내용 {i}", date(2014, 1, 1)) for i in range(5)
        ]
        vectors = [_dummy_vector(i) for i in range(5)]
        upsert_chunks(fresh_client, chunks, vectors)

        results = search_by_date(fresh_client, _dummy_vector(0), date(2024, 1, 1), top_k=3)
        assert len(results) <= 3


class TestRetrievalNodeFallback:
    """Gemini API 없을 때 retrieval_node가 빈 목록으로 fallback하는지 확인."""

    async def test_retrieval_node_fallback_when_no_api_key(self) -> None:
        """Gemini API 키 없으면 relevant_laws=[], HITL 경로로 진행."""
        from tax_copilot.agents.nodes.retrieval import tax_law_retrieval_node
        from tax_copilot.agents.state import AgentState

        state = AgentState(
            tenant_id=1,
            receipt_id=1,
            file_path="/tmp/test.jpg",  # noqa: S108
            file_hash="abc123",
            attempt_number=1,
            transaction_date=date(2024, 6, 15),
            law_as_of_date=date(2024, 6, 15),
            law_corpus_version="test",
            image_quality="ok",
            parsed_receipt=None,
            retrieval_query="부가세 매입세액 공제 신용카드",
            relevant_laws=[],
            calculation_result=None,
            draft_decision=None,
            final_decision=None,
            requires_human=False,
            error_message=None,
            messages=[],
        )

        # Gemini API 키 없이 실행 → ExternalServiceError → 빈 결과
        result = await tax_law_retrieval_node(state)
        assert result["relevant_laws"] == []
        assert "law_corpus_version" in result

    async def test_retrieval_node_with_mock_embedding(self) -> None:
        """embed_query를 mock하면 Qdrant에서 실제 결과를 반환한다."""
        from tax_copilot.agents.nodes.retrieval import tax_law_retrieval_node
        from tax_copilot.agents.state import AgentState

        # fresh_client에 chunk 삽입
        chunk = _make_chunk("vat-art38-mock-01", "매입세액 공제", date(2014, 1, 1))
        vector = _dummy_vector(0)
        upsert_chunks(get_client(in_memory=True), [chunk], [vector])

        state = AgentState(
            tenant_id=1,
            receipt_id=1,
            file_path="/tmp/test.jpg",  # noqa: S108
            file_hash="abc123",
            attempt_number=1,
            transaction_date=date(2024, 6, 15),
            law_as_of_date=date(2024, 6, 15),
            law_corpus_version="test",
            image_quality="ok",
            parsed_receipt=None,
            retrieval_query="부가세 매입세액 공제 신용카드",
            relevant_laws=[],
            calculation_result=None,
            draft_decision=None,
            final_decision=None,
            requires_human=False,
            error_message=None,
            messages=[],
        )

        with patch("tax_copilot.rag.search.embed_query", new_callable=AsyncMock) as mock_embed:
            mock_embed.return_value = vector
            with patch(
                "tax_copilot.rag.search.get_client", return_value=get_client(in_memory=True)
            ):  # noqa: E501
                result = await tax_law_retrieval_node(state)

        assert len(result["relevant_laws"]) >= 1
        assert result["relevant_laws"][0]["chunk_id"] == "vat-art38-mock-01"
