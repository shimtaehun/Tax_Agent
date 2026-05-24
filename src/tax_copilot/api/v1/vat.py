"""부가세 집계 API."""

from datetime import date

import structlog
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from tax_copilot.api.deps import CurrentUser, get_current_user, get_db
from tax_copilot.core.tax.aggregation import aggregate_vat
from tax_copilot.infra.db.models.receipt import (
    STATUS_APPROVED,
    STATUS_NEEDS_REVIEW,
    Receipt,
)
from tax_copilot.schemas.vat import AccountCodeSummary, VatGroup, VatSummaryResponse

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/vat", tags=["vat"])


@router.get("/summary", response_model=VatSummaryResponse)
async def get_vat_summary(
    client_company_id: int = Query(...),
    from_date: date = Query(...),
    to_date: date = Query(...),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> VatSummaryResponse:
    """기간별 부가세 매입세액 집계.

    거래일(transaction_date) 기준으로 필터링한다.
    STATUS_APPROVED 영수증만 집계에 포함하고,
    STATUS_NEEDS_REVIEW는 pending_review_count에만 반영한다.
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

    rows = [{"account_code": r.account_code, "parsed_data": r.parsed_data} for r in approved]
    summary = aggregate_vat(rows)

    logger.info(
        "vat.summary",
        tenant_id=current_user.tenant_id,
        client_company_id=client_company_id,
        from_date=str(from_date),
        to_date=str(to_date),
        approved_count=len(approved),
        pending_count=pending_count,
    )

    return VatSummaryResponse(
        client_company_id=client_company_id,
        from_date=from_date,
        to_date=to_date,
        creditable=VatGroup(**summary["creditable"]),
        non_creditable=VatGroup(**summary["non_creditable"]),
        pending_review_count=pending_count,
        by_account_code=[AccountCodeSummary(**item) for item in summary["by_account_code"]],
    )
