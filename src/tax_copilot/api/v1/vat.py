"""부가세 집계 API."""

from datetime import date

import structlog
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from tax_copilot.api.deps import CurrentUser, get_current_user, get_db
from tax_copilot.core.exceptions import AuthorizationError
from tax_copilot.core.tax.aggregation import aggregate_vat
from tax_copilot.infra.db.models.receipt import (
    STATUS_APPROVED,
    STATUS_NEEDS_REVIEW,
    Receipt,
)
from tax_copilot.infra.db.models.tax_invoice import INVOICE_DIRECTION_PURCHASE, TaxInvoice
from tax_copilot.infra.db.models.user import ROLE_CLIENT
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
    STATUS_APPROVED 영수증과 매입 세금계산서를 집계에 포함하고,
    STATUS_NEEDS_REVIEW는 pending_review_count에만 반영한다.
    """
    if current_user.role == ROLE_CLIENT:
        if current_user.client_company_id is None:
            raise AuthorizationError("client 계정에 고객사가 연결되어 있지 않습니다.")
        if client_company_id != current_user.client_company_id:
            raise AuthorizationError("다른 고객사의 부가세 집계에 접근할 수 없습니다.")

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

    invoice_result = await db.execute(
        select(TaxInvoice).where(
            TaxInvoice.tenant_id == current_user.tenant_id,
            TaxInvoice.client_company_id == client_company_id,
            TaxInvoice.issue_date >= from_date,
            TaxInvoice.issue_date <= to_date,
            TaxInvoice.direction == INVOICE_DIRECTION_PURCHASE,
        )
    )
    invoices = invoice_result.scalars().all()

    approved = [r for r in receipts if r.status == STATUS_APPROVED]
    pending_count = sum(1 for r in receipts if r.status == STATUS_NEEDS_REVIEW)

    rows = [{"account_code": r.account_code, "parsed_data": r.parsed_data} for r in approved]
    rows.extend(
        {
            "account_code": "매입세금계산서",
            "parsed_data": {
                "vat_creditable": True,
                "calculation_result": {
                    "supply_value_krw": i.supply_value_krw,
                    "vat_krw": i.vat_krw,
                },
            },
        }
        for i in invoices
    )
    summary = aggregate_vat(rows)

    logger.info(
        "vat.summary",
        tenant_id=current_user.tenant_id,
        client_company_id=client_company_id,
        from_date=str(from_date),
        to_date=str(to_date),
        approved_count=len(approved),
        invoice_count=len(invoices),
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
