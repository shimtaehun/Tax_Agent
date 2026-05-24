"""LangGraph AgentState 정의.

원칙:
- state에 원본 이미지 bytes를 넣지 않는다.
- file_path, receipt_id, thread_id 등 ID와 경로만 저장한다.
- 재개 가능성과 checkpointer 직렬화를 위해 모든 값은 JSON-serializable이어야 한다.
"""

from datetime import date
from typing import Annotated, NotRequired

from langgraph.graph.message import add_messages
from typing_extensions import TypedDict


class AgentState(TypedDict):
    # 식별자 — 실행 중 변경 없음
    tenant_id: int
    receipt_id: int
    file_path: str
    file_hash: str
    attempt_number: int

    # 거래일 — 법령 검색 기준
    transaction_date: date | None
    law_as_of_date: date | None  # 검색에 사용할 확정 날짜
    law_corpus_version: str

    # 처리 단계별 결과
    image_quality: str | None  # "ok" | "unreadable" | "low"
    parsed_receipt: dict | None  # ParsedReceipt.model_dump()
    retrieval_query: str | None
    relevant_laws: list[dict]  # LawChunk.model_dump() 목록

    calculation_result: dict | None  # VAT, 손금산입 계산 결과
    draft_decision: dict | None  # TaxDecision 초안
    final_decision: dict | None  # 세무사 검토 후 확정

    # 중복 감지 결과
    duplicate_suspect: NotRequired[bool]
    duplicate_receipt_ids: NotRequired[list[int]]

    # 제어 플래그
    requires_human: bool
    error_message: str | None

    # LangGraph 메시지 (add_messages reducer로 누적)
    messages: Annotated[list, add_messages]
