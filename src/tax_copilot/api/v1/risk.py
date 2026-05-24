"""세무조사 리스크 스코어링 API."""

from datetime import date

import structlog
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from tax_copilot.api.deps import CurrentUser, get_current_user, get_db
from tax_copilot.core.tax.risk_scoring import score_risk
from tax_copilot.infra.db.models.receipt import (
    STATUS_APPROVED,
    STATUS_NEEDS_REVIEW,
    Receipt,
)
from tax_copilot.schemas.risk import RiskIndicators, RiskScoreResponse

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/risk", tags=["risk"])


@router.get("/score", response_model=RiskScoreResponse)
async def get_risk_score(
    client_company_id: int = Query(...),
    from_date: date = Query(...),
    to_date: date = Query(...),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> RiskScoreResponse:
    """고객사의 세무조사 리스크 점수를 반환한다.

    거래일(transaction_date) 기준으로 필터링한다.
    STATUS_APPROVED 영수증만 지표 계산에 포함한다.
    """
    result = await db.execute(
        select(Receipt).where(
            Receipt.tenant_id == current_user.tenant_id,
            Receipt.client_company_id == client_company_id,
            Receipt.transaction_date >= from_date,
            Receipt.transaction_date <= to_date,
            Receipt.status.in_([STATUS_APPROVED, STATUS_NEEDS_REVIEW]),
        )
    )
    receipts = result.scalars().all()

    approved = [r for r in receipts if r.status == STATUS_APPROVED]
    pending_count = sum(1 for r in receipts if r.status == STATUS_NEEDS_REVIEW)

    total_supply = 0
    entertainment_supply = 0
    simplified_count = 0
    risk_flag_count = 0
    duplicate_count = 0

    for r in approved:
        parsed = r.parsed_data or {}
        calc = parsed.get("calculation_result") or {}
        supply = int(calc.get("supply_value_krw") or 0)
        total_supply += supply

        if r.account_code == "접대비":
            entertainment_supply += supply

        if parsed.get("evidence_type") == "simplified_receipt":
            simplified_count += 1

        if parsed.get("risk_flags"):
            risk_flag_count += 1

        if r.duplicate_suspect:
            duplicate_count += 1

    stats = {
        "total_approved": len(approved),
        "total_supply_value_krw": total_supply,
        "entertainment_supply_value_krw": entertainment_supply,
        "simplified_receipt_count": simplified_count,
        "risk_flag_count": risk_flag_count,
        "duplicate_suspect_count": duplicate_count,
    }
    result_dict = score_risk(stats)

    logger.info(
        "risk.score",
        tenant_id=current_user.tenant_id,
        client_company_id=client_company_id,
        score=result_dict["score"],
    )

    return RiskScoreResponse(
        client_company_id=client_company_id,
        from_date=from_date,
        to_date=to_date,
        score=int(result_dict["score"]),
        flags=list(result_dict["flags"]),
        explanation=str(result_dict["explanation"]),
        indicators=RiskIndicators(**result_dict["indicators"]),
        total_approved=len(approved),
        pending_review_count=pending_count,
    )
