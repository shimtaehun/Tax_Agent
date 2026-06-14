"""카드사 결제내역(엑셀) 업로드·조회 API."""

from datetime import date

import structlog
from fastapi import APIRouter, Depends, Query, UploadFile
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from tax_copilot.api.deps import CurrentUser, get_current_user, get_db
from tax_copilot.auth.permissions import require_staff_or_admin
from tax_copilot.core.exceptions import AuthorizationError, ValidationError
from tax_copilot.core.statements.ingest import ingest_statement_rows
from tax_copilot.core.statements.registry import detect_parser, get_parser
from tax_copilot.infra.db.models.card_transaction import CardTransaction
from tax_copilot.infra.db.models.user import ROLE_CLIENT
from tax_copilot.schemas.statements import (
    StatementListResponse,
    StatementTransactionItem,
    StatementUploadResponse,
)

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/statements", tags=["statements"])


def _authorize_company(current_user: CurrentUser, client_company_id: int) -> None:
    if current_user.role != ROLE_CLIENT:
        return
    if current_user.client_company_id is None:
        raise AuthorizationError("client 계정에 고객사가 연결되어 있지 않습니다.")
    if client_company_id != current_user.client_company_id:
        raise AuthorizationError("다른 고객사의 결제내역에 접근할 수 없습니다.")


def _to_item(txn: CardTransaction) -> StatementTransactionItem:
    return StatementTransactionItem(
        id=txn.id,
        client_company_id=txn.client_company_id,
        card_company=txn.card_company,
        transaction_date=txn.transaction_date,
        transaction_time=txn.transaction_time,
        merchant_name=txn.merchant_name,
        approval_no=txn.approval_no,
        card_no_masked=txn.card_no_masked,
        total_amount_krw=txn.total_amount_krw,
        installment_months=txn.installment_months,
        account_code=txn.account_code,
        cancelled=txn.cancelled,
        status=txn.status,
        source_filename=txn.source_filename,
        created_at=txn.created_at,
    )


@router.post("/upload", response_model=StatementUploadResponse, status_code=201)
async def upload_statement(
    file: UploadFile,
    client_company_id: int = Query(...),
    card_company: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> StatementUploadResponse:
    """카드사 엑셀 결제목록을 파싱해 거래로 적재한다.

    card_company를 지정하면 해당 파서를 쓰고, 생략하면 파일명으로 자동 판별한다.
    """
    require_staff_or_admin(current_user.role)
    if file.filename is None:
        raise ValidationError("파일명이 없습니다.")

    content = await file.read()

    if card_company:
        parser = get_parser(card_company)
    else:
        parser = detect_parser(file.filename, [])
        if parser is None:
            raise ValidationError("카드사를 판별할 수 없습니다. card_company를 지정해 주세요.")

    rows = parser.parse(file.filename, content)
    result = await ingest_statement_rows(
        db,
        rows,
        tenant_id=current_user.tenant_id,
        client_company_id=client_company_id,
        uploaded_by=current_user.user_id,
        source_filename=file.filename,
        card_company=parser.card_company,
    )

    logger.info(
        "statements.imported",
        tenant_id=current_user.tenant_id,
        client_company_id=client_company_id,
        card_company=parser.card_company,
        imported_count=result.imported,
        skipped_count=result.skipped,
    )
    return StatementUploadResponse(
        card_company=parser.card_company,
        imported_count=result.imported,
        skipped_count=result.skipped,
        total_count=result.total,
    )


@router.get("", response_model=StatementListResponse)
async def list_statements(
    client_company_id: int = Query(...),
    from_date: date | None = Query(default=None),
    to_date: date | None = Query(default=None),
    card_company: str | None = Query(default=None),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> StatementListResponse:
    """적재된 카드 결제내역을 거래일 최신순으로 조회한다."""
    _authorize_company(current_user, client_company_id)
    filters = [
        CardTransaction.tenant_id == current_user.tenant_id,
        CardTransaction.client_company_id == client_company_id,
    ]
    if from_date is not None:
        filters.append(CardTransaction.transaction_date >= from_date)
    if to_date is not None:
        filters.append(CardTransaction.transaction_date <= to_date)
    if card_company is not None:
        filters.append(CardTransaction.card_company == card_company)

    total_result = await db.execute(
        select(func.count()).select_from(CardTransaction).where(*filters)
    )
    result = await db.execute(
        select(CardTransaction)
        .where(*filters)
        .order_by(CardTransaction.transaction_date.desc(), CardTransaction.id.desc())
        .offset(skip)
        .limit(limit)
    )
    return StatementListResponse(
        items=[_to_item(t) for t in result.scalars().all()],
        total=total_result.scalar_one(),
    )
