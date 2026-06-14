"""RAG 검색 파이프라인.

외부 진입점: search_tax_law()
- 쿼리 임베딩 (Gemini)
- 거래일 기준 Qdrant 검색
- 결과를 dict 목록으로 반환 (AgentState.relevant_laws와 호환)

Gemini API 키 없으면 ExternalServiceError를 발생시킨다.
"""

from datetime import date

from tax_copilot.core.exceptions import ExternalServiceError
from tax_copilot.infra.gemini.embedding import embed_query
from tax_copilot.infra.vector.qdrant import get_client, search_by_date


async def search_tax_law(
    query: str,
    as_of_date: date,
    top_k: int = 3,
) -> list[dict]:
    """거래일 기준으로 관련 법령 chunk를 검색한다.

    Args:
        query: 법령 검색 쿼리 (예: "부가세 매입세액 공제 신용카드")
        as_of_date: 거래일 (법령 시행일 기준 필터)
        top_k: 반환할 최대 chunk 수

    Returns:
        relevant_laws 형식의 dict 목록. 각 항목은 LawChunk 필드 + score.

    Raises:
        ExternalServiceError: Gemini API 호출 실패 시
    """
    try:
        query_vector = await embed_query(query)
    except RuntimeError as exc:
        raise ExternalServiceError(f"Gemini 임베딩 오류: {exc}") from exc
    except Exception as exc:
        raise ExternalServiceError(f"임베딩 중 예상치 못한 오류: {exc}") from exc

    client = get_client()
    return search_by_date(client, query_vector, as_of_date, top_k=top_k)
