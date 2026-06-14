"""누락 증빙 감지 + 고객 요청 목록 API.

카드내역에는 있으나 영수증(증빙)이 없는 결제를 고객사별로 모아, 그대로 전달
가능한 요청 문구까지 만들어준다.
- GET /missing-evidence : 누락 증빙 목록 + 요청 문구
"""

from datetime import date

import structlog
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from tax_copilot.api.deps import CurrentUser, get_current_user, get_db
from tax_copilot.core.exceptions import AuthorizationError
from tax_copilot.core.tax.missing_evidence import (
    CardCharge,
    ReceiptRef,
    find_cards_missing_receipts,
)
from tax_copilot.infra.db.models.card_transaction import CardTransaction
from tax_copilot.infra.db.models.receipt import STATUS_APPROVED, STATUS_NEEDS_REVIEW, Receipt
from tax_copilot.infra.db.models.user import ROLE_CLIENT
from tax_copilot.schemas.missing_evidence import (
    MissingEvidenceCard,
    MissingEvidenceResponse,
)

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/missing-evidence", tags=["missing-evidence"])


def _authorize_company(current_user: CurrentUser, client_company_id: int) -> None:
    if current_user.role != ROLE_CLIENT:
        return
    if current_user.client_company_id is None:
        raise AuthorizationError("client 계정에 고객사가 연결되어 있지 않습니다.")
    if client_company_id != current_user.client_company_id:
        raise AuthorizationError("다른 고객사의 증빙 현황에 접근할 수 없습니다.")


def _receipt_amount(receipt: Receipt) -> int:
    parsed = receipt.parsed_data or {}
    calc = parsed.get("calculation_result") or {}
    return int(calc.get("supply_value_krw") or 0) + int(calc.get("vat_krw") or 0)


def _build_request_message(items: list[MissingEvidenceCard], total_krw: int) -> str:
    if not items:
        return "누락된 증빙이 없습니다. 모든 카드 결제에 증빙이 확인됩니다."
    lines = [
        f"아래 {len(items)}건의 카드 결제에 대한 증빙(영수증/세금계산서)이 확인되지 않습니다.",
        f"총 {total_krw:,}원. 해당 증빙을 전달 부탁드립니다.",
        "",
    ]
    for it in items:
        d = it.transaction_date.isoformat() if it.transaction_date else "날짜미상"
        merchant = it.merchant_name or "가맹점미상"
        lines.append(f"- {d} / {merchant} / {it.amount_krw:,}원")
    return "\n".join(lines)


@router.get("", response_model=MissingEvidenceResponse)
async def get_missing_evidence(
    client_company_id: int = Query(...),
    from_date: date = Query(...),
    to_date: date = Query(...),
    date_tolerance_days: int = Query(default=3, ge=0, le=31),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> MissingEvidenceResponse:
    """카드 결제 중 대응 영수증이 없는 건을 가려낸다."""
    _authorize_company(current_user, client_company_id)

    cards = (
        (
            await db.execute(
                select(CardTransaction).where(
                    CardTransaction.tenant_id == current_user.tenant_id,
                    CardTransaction.client_company_id == client_company_id,
                    CardTransaction.transaction_date >= from_date,
                    CardTransaction.transaction_date <= to_date,
                    CardTransaction.cancelled.is_(False),
                )
            )
        )
        .scalars()
        .all()
    )

    receipts = (
        (
            await db.execute(
                select(Receipt).where(
                    Receipt.tenant_id == current_user.tenant_id,
                    Receipt.client_company_id == client_company_id,
                    Receipt.transaction_date >= from_date,
                    Receipt.transaction_date <= to_date,
                    Receipt.status.in_([STATUS_APPROVED, STATUS_NEEDS_REVIEW]),
                )
            )
        )
        .scalars()
        .all()
    )

    card_charges = [
        CardCharge(
            id=c.id,
            amount_krw=c.total_amount_krw or 0,
            transaction_date=c.transaction_date,
            merchant_name=c.merchant_name,
        )
        for c in cards
        if c.total_amount_krw
    ]
    receipt_refs = [
        ReceiptRef(id=r.id, amount_krw=_receipt_amount(r), transaction_date=r.transaction_date)
        for r in receipts
        if _receipt_amount(r) > 0
    ]

    missing = find_cards_missing_receipts(
        card_charges, receipt_refs, date_tolerance_days=date_tolerance_days
    )

    items = [
        MissingEvidenceCard(
            card_transaction_id=m.id,
            transaction_date=m.transaction_date,
            merchant_name=m.merchant_name,
            amount_krw=m.amount_krw,
        )
        for m in missing
    ]
    missing_total = sum(it.amount_krw for it in items)

    logger.info(
        "missing_evidence.report",
        tenant_id=current_user.tenant_id,
        client_company_id=client_company_id,
        card_count=len(card_charges),
        missing_count=len(items),
    )

    return MissingEvidenceResponse(
        client_company_id=client_company_id,
        from_date=from_date,
        to_date=to_date,
        card_count=len(card_charges),
        receipt_count=len(receipt_refs),
        missing_count=len(items),
        missing_amount_krw=missing_total,
        items=items,
        request_message=_build_request_message(items, missing_total),
    )
