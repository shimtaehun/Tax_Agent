"""법령 검색 노드.

Phase 3: Qdrant + Gemini embedding으로 거래일 기준 법령 검색.
Gemini API 키 없으면 ExternalServiceError → HITL 경로로 fallback.
"""

from datetime import date

from tax_copilot.agents.state import AgentState
from tax_copilot.core.exceptions import ExternalServiceError

_CORPUS_VERSION = "phase3-v1"


async def build_retrieval_query_node(state: AgentState) -> dict:
    """parsed_receipt 기반으로 법령 검색 쿼리를 생성한다."""
    parsed = state.get("parsed_receipt") or {}
    evidence_type = parsed.get("evidence_type", "unknown")
    payment_method = parsed.get("payment_method", "")

    query = f"부가세 매입세액 공제 {evidence_type} {payment_method}".strip()
    return {"retrieval_query": query}


async def tax_law_retrieval_node(state: AgentState) -> dict:
    """거래일 기준 법령 chunk를 Qdrant에서 검색한다.

    Gemini API 키 없거나 Qdrant 연결 실패 시:
    - relevant_laws = [] 로 반환
    - audit_prepare_node가 requires_human=True로 HITL 경로 선택
    """
    query = state.get("retrieval_query") or ""
    as_of_date: date | None = state.get("law_as_of_date")

    if not query or as_of_date is None:
        return {"relevant_laws": [], "law_corpus_version": _CORPUS_VERSION}

    try:
        from tax_copilot.rag.search import search_tax_law

        results = await search_tax_law(query, as_of_date)
        return {"relevant_laws": results, "law_corpus_version": _CORPUS_VERSION}
    except ExternalServiceError:
        # Gemini API 없거나 Qdrant 없음 → 빈 결과, HITL fallback
        return {"relevant_laws": [], "law_corpus_version": _CORPUS_VERSION}
    except Exception:
        return {"relevant_laws": [], "law_corpus_version": _CORPUS_VERSION}
