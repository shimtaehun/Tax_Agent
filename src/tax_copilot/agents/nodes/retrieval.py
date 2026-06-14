"""법령 검색 노드.

Phase 3: Qdrant + Gemini embedding으로 거래일 기준 법령 검색.
Gemini API 키 없으면 ExternalServiceError → HITL 경로로 fallback.
"""

from datetime import date

from tax_copilot.agents.state import AgentState
from tax_copilot.core.exceptions import ExternalServiceError

_CORPUS_VERSION = "phase3-v1"


_EVIDENCE_QUERY: dict[str, str] = {
    # 한국어 키 (법령 내 용어)
    "세금계산서": "세금계산서 매입세액 공제 요건 필요적 기재사항",
    "신용카드영수증": "신용카드 매입세액 공제 사업 관련 지출",
    "현금영수증": "현금영수증 매입세액 공제 사업자",
    "간이영수증": "간이영수증 매입세액 공제 불공제",
    "계산서": "계산서 면세 매입세액 불공제",
    # 영어 키 (Gemini Vision 출력 형식)
    "tax_invoice": "세금계산서 매입세액 공제 요건 필요적 기재사항",
    "credit_card_slip": "신용카드 매입세액 공제 사업 관련 지출",
    "cash_receipt": "현금영수증 매입세액 공제 사업자",
    "simple_receipt": "간이영수증 매입세액 공제 불공제",
    "receipt": "부가가치세 매입세액 공제 요건 영수증 사업 관련성",
    "invoice": "계산서 면세 매입세액 불공제",
}


async def build_retrieval_query_node(state: AgentState) -> dict:
    """parsed_receipt 기반으로 법령 검색 쿼리를 생성한다."""
    parsed = state.get("parsed_receipt") or {}
    evidence_type = parsed.get("evidence_type", "unknown")

    query = _EVIDENCE_QUERY.get(evidence_type, "부가가치세 매입세액 공제 요건 사업 관련성")
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
