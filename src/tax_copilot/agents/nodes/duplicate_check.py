"""중복 영수증 감지 노드.

같은 tenant의 기존 승인/검토 영수증 중 상호명 유사도 >= 80 AND 금액 동일인 것을
중복 의심 영수증으로 표시한다.
"""

import structlog
from rapidfuzz import fuzz
from sqlalchemy import select

from tax_copilot.agents.state import AgentState
from tax_copilot.infra.database import AsyncSessionLocal
from tax_copilot.infra.db.models.receipt import Receipt

logger = structlog.get_logger(__name__)

_STATUS_APPROVED = "approved"
_STATUS_NEEDS_REVIEW = "needs_review"
_MIN_CONFIDENCE = 0.75
_SIMILARITY_THRESHOLD = 80


async def duplicate_check_node(state: AgentState) -> dict:
    """중복 영수증 여부를 감지한다."""
    parsed = state.get("parsed_receipt") or {}
    confidence = parsed.get("extraction_confidence", 0.0)
    merchant_name = parsed.get("merchant_name")
    total_amount = parsed.get("total_amount_krw")

    if confidence < _MIN_CONFIDENCE or not merchant_name or total_amount is None:
        return {"duplicate_suspect": False, "duplicate_receipt_ids": []}

    try:
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(Receipt).where(
                    Receipt.tenant_id == state["tenant_id"],
                    Receipt.id != state["receipt_id"],
                    Receipt.status.in_([_STATUS_APPROVED, _STATUS_NEEDS_REVIEW]),
                    Receipt.parsed_data.is_not(None),
                )
            )
            candidates = result.scalars().all()
    except Exception:
        logger.exception("duplicate_check_node: DB 조회 실패, 중복 감지 생략")
        return {"duplicate_suspect": False, "duplicate_receipt_ids": []}

    duplicate_ids: list[int] = []
    for candidate in candidates:
        c_data = candidate.parsed_data or {}
        c_name = c_data.get("merchant_name")
        c_amount = c_data.get("total_amount_krw")
        if c_name is None or c_amount != total_amount:
            continue
        if fuzz.partial_ratio(merchant_name, c_name) >= _SIMILARITY_THRESHOLD:
            duplicate_ids.append(candidate.id)

    return {
        "duplicate_suspect": len(duplicate_ids) > 0,
        "duplicate_receipt_ids": duplicate_ids,
    }
