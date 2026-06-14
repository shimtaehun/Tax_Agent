"""통장 거래내역 업로드·조회 + 삼중 대사(reconciliation) API.

- POST /bank/upload                 : 통장 CSV 업로드(범용 파서)
- GET  /bank/transactions           : 통장 거래 목록
- GET  /bank/reconciliation         : 통장 ↔ 카드 ↔ 세금계산서 대사 미리보기
- POST /bank/reconciliation/apply   : 대사 결과를 통장 거래에 반영(matched 표시)
"""

from datetime import date

import structlog
from fastapi import APIRouter, Depends, Query, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from tax_copilot.api.deps import CurrentUser, get_current_user, get_db
from tax_copilot.core.bank import parse_bank_csv
from tax_copilot.core.exceptions import AuthorizationError, ValidationError
from tax_copilot.core.tax.reconciliation import (
    BankItem,
    ReconCandidate,
    reconcile,
)
from tax_copilot.infra.db.models.bank_transaction import BankTransaction
from tax_copilot.infra.db.models.card_transaction import CardTransaction
from tax_copilot.infra.db.models.tax_invoice import (
    INVOICE_DIRECTION_SALE,
    TaxInvoice,
)
from tax_copilot.infra.db.models.user import ROLE_CLIENT
from tax_copilot.schemas.bank import (
    BankListResponse,
    BankTransactionItem,
    BankUploadResponse,
    ReconciliationResponse,
    ReconMatchItem,
    ReconUnmatchedCandidate,
)

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/bank", tags=["bank"])


def _authorize_company(current_user: CurrentUser, client_company_id: int) -> None:
    if current_user.role != ROLE_CLIENT:
        return
    if current_user.client_company_id is None:
        raise AuthorizationError("client 계정에 고객사가 연결되어 있지 않습니다.")
    if client_company_id != current_user.client_company_id:
        raise AuthorizationError("다른 고객사의 통장내역에 접근할 수 없습니다.")


def _to_item(txn: BankTransaction) -> BankTransactionItem:
    return BankTransactionItem(
        id=txn.id,
        client_company_id=txn.client_company_id,
        bank_name=txn.bank_name,
        account_no_masked=txn.account_no_masked,
        transaction_date=txn.transaction_date,
        description=txn.description,
        counterparty=txn.counterparty,
        deposit_krw=txn.deposit_krw,
        withdrawal_krw=txn.withdrawal_krw,
        balance_krw=txn.balance_krw,
        matched=txn.matched,
        matched_source_type=txn.matched_source_type,
        matched_source_id=txn.matched_source_id,
        source_filename=txn.source_filename,
        created_at=txn.created_at,
    )


@router.post("/upload", response_model=BankUploadResponse, status_code=201)
async def upload_bank_csv(
    file: UploadFile,
    client_company_id: int = Query(...),
    bank_name: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> BankUploadResponse:
    """범용 통장 거래내역 CSV를 업로드한다."""
    _authorize_company(current_user, client_company_id)
    raw = await file.read()
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = raw.decode("cp949", errors="replace")

    rows = parse_bank_csv(text)
    if not rows:
        raise ValidationError(
            "통장 CSV에서 거래를 인식하지 못했습니다. 헤더(거래일자/출금/입금)를 확인하세요."
        )

    imported = 0
    skipped = 0
    items: list[BankTransaction] = []
    for row in rows:
        existing = (
            await db.execute(
                select(BankTransaction).where(
                    BankTransaction.tenant_id == current_user.tenant_id,
                    BankTransaction.client_company_id == client_company_id,
                    BankTransaction.transaction_date == row.transaction_date,
                    BankTransaction.description == row.description,
                    BankTransaction.deposit_krw == row.deposit_krw,
                    BankTransaction.withdrawal_krw == row.withdrawal_krw,
                    BankTransaction.balance_krw == row.balance_krw,
                )
            )
        ).scalar_one_or_none()
        if existing is not None:
            skipped += 1
            continue
        txn = BankTransaction(
            tenant_id=current_user.tenant_id,
            client_company_id=client_company_id,
            uploaded_by=current_user.user_id,
            bank_name=bank_name,
            source_filename=file.filename or "bank.csv",
            transaction_date=row.transaction_date,
            description=row.description,
            counterparty=row.counterparty,
            deposit_krw=row.deposit_krw,
            withdrawal_krw=row.withdrawal_krw,
            balance_krw=row.balance_krw,
        )
        db.add(txn)
        items.append(txn)
        imported += 1

    await db.commit()
    for txn in items:
        await db.refresh(txn)

    logger.info(
        "bank.upload",
        tenant_id=current_user.tenant_id,
        client_company_id=client_company_id,
        imported=imported,
        skipped=skipped,
    )
    return BankUploadResponse(
        imported_count=imported,
        skipped_count=skipped,
        items=[_to_item(t) for t in items],
    )


@router.get("/transactions", response_model=BankListResponse)
async def list_bank_transactions(
    client_company_id: int = Query(...),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> BankListResponse:
    _authorize_company(current_user, client_company_id)
    rows = (
        (
            await db.execute(
                select(BankTransaction)
                .where(
                    BankTransaction.tenant_id == current_user.tenant_id,
                    BankTransaction.client_company_id == client_company_id,
                )
                .order_by(BankTransaction.transaction_date.desc(), BankTransaction.id.desc())
            )
        )
        .scalars()
        .all()
    )
    return BankListResponse(items=[_to_item(t) for t in rows], total=len(rows))


async def _build_candidates(
    db: AsyncSession,
    tenant_id: int,
    client_company_id: int,
    from_date: date,
    to_date: date,
) -> list[ReconCandidate]:
    """기간 내 카드내역·세금계산서를 대사 후보(예상 현금흐름)로 변환한다."""
    candidates: list[ReconCandidate] = []

    cards = (
        (
            await db.execute(
                select(CardTransaction).where(
                    CardTransaction.tenant_id == tenant_id,
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
    for c in cards:
        if c.total_amount_krw:
            candidates.append(
                ReconCandidate(
                    source_type="card",
                    source_id=c.id,
                    amount_krw=c.total_amount_krw,
                    transaction_date=c.transaction_date,
                    direction="out",
                    label=c.merchant_name,
                )
            )

    invoices = (
        (
            await db.execute(
                select(TaxInvoice).where(
                    TaxInvoice.tenant_id == tenant_id,
                    TaxInvoice.client_company_id == client_company_id,
                    TaxInvoice.issue_date >= from_date,
                    TaxInvoice.issue_date <= to_date,
                )
            )
        )
        .scalars()
        .all()
    )
    for i in invoices:
        is_sale = i.direction == INVOICE_DIRECTION_SALE
        candidates.append(
            ReconCandidate(
                source_type="tax_invoice_sale" if is_sale else "tax_invoice_purchase",
                source_id=i.id,
                amount_krw=i.total_amount_krw,
                transaction_date=i.issue_date,
                direction="in" if is_sale else "out",
                label=i.recipient_name if is_sale else i.supplier_name,
            )
        )

    return candidates


@router.get("/reconciliation", response_model=ReconciliationResponse)
async def get_reconciliation(
    client_company_id: int = Query(...),
    from_date: date = Query(...),
    to_date: date = Query(...),
    date_tolerance_days: int = Query(default=3, ge=0, le=31),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> ReconciliationResponse:
    """통장 ↔ 카드 ↔ 세금계산서 삼중 대사 미리보기."""
    _authorize_company(current_user, client_company_id)

    bank_rows = (
        (
            await db.execute(
                select(BankTransaction).where(
                    BankTransaction.tenant_id == current_user.tenant_id,
                    BankTransaction.client_company_id == client_company_id,
                    BankTransaction.transaction_date >= from_date,
                    BankTransaction.transaction_date <= to_date,
                )
            )
        )
        .scalars()
        .all()
    )

    candidates = await _build_candidates(
        db, current_user.tenant_id, client_company_id, from_date, to_date
    )

    result = reconcile(
        [
            BankItem(
                id=b.id,
                transaction_date=b.transaction_date,
                deposit_krw=b.deposit_krw,
                withdrawal_krw=b.withdrawal_krw,
            )
            for b in bank_rows
        ],
        candidates,
        date_tolerance_days=date_tolerance_days,
    )

    bank_by_id = {b.id: b for b in bank_rows}
    unmatched_bank = [_to_item(bank_by_id[bid]) for bid in result.unmatched_bank_ids]

    logger.info(
        "bank.reconciliation",
        tenant_id=current_user.tenant_id,
        client_company_id=client_company_id,
        bank_count=len(bank_rows),
        matched=result.matched_count,
        unmatched_bank=len(unmatched_bank),
    )

    return ReconciliationResponse(
        client_company_id=client_company_id,
        from_date=from_date,
        to_date=to_date,
        bank_count=len(bank_rows),
        candidate_count=len(candidates),
        matched_count=result.matched_count,
        matches=[
            ReconMatchItem(
                bank_id=m.bank_id,
                source_type=m.source_type,
                source_id=m.source_id,
                amount_krw=m.amount_krw,
            )
            for m in result.matches
        ],
        unmatched_bank=unmatched_bank,
        unmatched_candidates=[
            ReconUnmatchedCandidate(
                source_type=c.source_type,
                source_id=c.source_id,
                amount_krw=c.amount_krw,
                transaction_date=c.transaction_date,
                direction=c.direction,
                label=c.label,
            )
            for c in result.unmatched_candidates
        ],
    )


@router.post("/reconciliation/apply")
async def apply_reconciliation(
    client_company_id: int = Query(...),
    from_date: date = Query(...),
    to_date: date = Query(...),
    date_tolerance_days: int = Query(default=3, ge=0, le=31),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> dict[str, int]:
    """대사 결과를 통장 거래에 반영한다(matched 플래그 + 매칭 소스 기록)."""
    _authorize_company(current_user, client_company_id)

    bank_rows = (
        (
            await db.execute(
                select(BankTransaction).where(
                    BankTransaction.tenant_id == current_user.tenant_id,
                    BankTransaction.client_company_id == client_company_id,
                    BankTransaction.transaction_date >= from_date,
                    BankTransaction.transaction_date <= to_date,
                )
            )
        )
        .scalars()
        .all()
    )
    candidates = await _build_candidates(
        db, current_user.tenant_id, client_company_id, from_date, to_date
    )
    result = reconcile(
        [
            BankItem(
                id=b.id,
                transaction_date=b.transaction_date,
                deposit_krw=b.deposit_krw,
                withdrawal_krw=b.withdrawal_krw,
            )
            for b in bank_rows
        ],
        candidates,
        date_tolerance_days=date_tolerance_days,
    )

    bank_by_id = {b.id: b for b in bank_rows}
    matched_ids = set()
    for m in result.matches:
        txn = bank_by_id.get(m.bank_id)
        if txn is not None:
            txn.matched = True
            txn.matched_source_type = m.source_type
            txn.matched_source_id = m.source_id
            matched_ids.add(m.bank_id)
    # 매칭 안 된 통장 거래는 matched=False로 되돌린다(재실행 멱등성).
    for b in bank_rows:
        if b.id not in matched_ids:
            b.matched = False
            b.matched_source_type = None
            b.matched_source_id = None

    await db.commit()
    return {"matched": len(matched_ids), "unmatched": len(result.unmatched_bank_ids)}
