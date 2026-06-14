"""분개(전표) 자동 생성 + 회계프로그램 import용 CSV export API.

승인된 영수증과 세금계산서를 거래일 기준으로 모아 복식부기 전표로 변환한다.
- GET /journal/entries     : 전표 미리보기(JSON)
- GET /journal/export.csv  : 회계프로그램 import용 CSV 다운로드
"""

from datetime import date
from urllib.parse import quote

import structlog
from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from tax_copilot.api.deps import CurrentUser, get_current_user, get_db
from tax_copilot.core.exceptions import AuthorizationError
from tax_copilot.core.tax.journal import (
    JournalEntry,
    build_entry_from_receipt,
    build_entry_from_tax_invoice,
)
from tax_copilot.core.tax.journal_export import journal_entries_to_csv
from tax_copilot.infra.db.models.receipt import STATUS_APPROVED, Receipt
from tax_copilot.infra.db.models.tax_invoice import TaxInvoice
from tax_copilot.infra.db.models.user import ROLE_CLIENT
from tax_copilot.schemas.journal import (
    JournalEntryOut,
    JournalLineOut,
    JournalPreviewResponse,
)

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/journal", tags=["journal"])

# UTF-8 BOM: Excel·국내 회계프로그램이 한글 CSV를 깨짐 없이 인식하도록.
_UTF8_BOM = "﻿"


async def _collect_entries(
    db: AsyncSession,
    current_user: CurrentUser,
    client_company_id: int,
    from_date: date,
    to_date: date,
) -> list[JournalEntry]:
    """기간 내 승인 영수증 + 세금계산서를 전표 목록으로 변환한다."""
    if current_user.role == ROLE_CLIENT:
        if current_user.client_company_id is None:
            raise AuthorizationError("client 계정에 고객사가 연결되어 있지 않습니다.")
        if client_company_id != current_user.client_company_id:
            raise AuthorizationError("다른 고객사의 전표에 접근할 수 없습니다.")

    receipt_result = await db.execute(
        select(Receipt).where(
            Receipt.tenant_id == current_user.tenant_id,
            Receipt.client_company_id == client_company_id,
            Receipt.transaction_date >= from_date,
            Receipt.transaction_date <= to_date,
            Receipt.status == STATUS_APPROVED,
        )
    )
    receipts = receipt_result.scalars().all()

    invoice_result = await db.execute(
        select(TaxInvoice).where(
            TaxInvoice.tenant_id == current_user.tenant_id,
            TaxInvoice.client_company_id == client_company_id,
            TaxInvoice.issue_date >= from_date,
            TaxInvoice.issue_date <= to_date,
        )
    )
    invoices = invoice_result.scalars().all()

    entries: list[JournalEntry] = []
    for r in receipts:
        entry = build_entry_from_receipt(
            {
                "id": r.id,
                "transaction_date": r.transaction_date,
                "account_code": r.account_code,
                "parsed_data": r.parsed_data,
            }
        )
        if entry is not None:
            entries.append(entry)

    for i in invoices:
        entry = build_entry_from_tax_invoice(
            {
                "id": i.id,
                "direction": i.direction,
                "issue_date": i.issue_date,
                "supplier_name": i.supplier_name,
                "recipient_name": i.recipient_name,
                "supply_value_krw": i.supply_value_krw,
                "vat_krw": i.vat_krw,
            }
        )
        if entry is not None:
            entries.append(entry)

    entries.sort(key=lambda e: e.entry_date)
    return entries


@router.get("/entries", response_model=JournalPreviewResponse)
async def preview_journal_entries(
    client_company_id: int = Query(...),
    from_date: date = Query(...),
    to_date: date = Query(...),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> JournalPreviewResponse:
    """기간별 자동 생성 전표 미리보기."""
    entries = await _collect_entries(db, current_user, client_company_id, from_date, to_date)

    items = [
        JournalEntryOut(
            entry_date=e.entry_date,
            summary=e.summary,
            source_type=e.source_type,
            source_id=e.source_id,
            counterparty=e.counterparty,
            debit_total=e.debit_total,
            credit_total=e.credit_total,
            balanced=e.is_balanced,
            lines=[
                JournalLineOut(
                    side=line.side,
                    account_title=line.account_title,
                    amount_krw=line.amount_krw,
                    description=line.description,
                )
                for line in e.lines
            ],
        )
        for e in entries
    ]
    debit_total = sum(e.debit_total for e in entries)
    credit_total = sum(e.credit_total for e in entries)

    logger.info(
        "journal.preview",
        tenant_id=current_user.tenant_id,
        client_company_id=client_company_id,
        entry_count=len(entries),
    )

    return JournalPreviewResponse(
        client_company_id=client_company_id,
        from_date=from_date,
        to_date=to_date,
        entry_count=len(entries),
        debit_total=debit_total,
        credit_total=credit_total,
        balanced=debit_total == credit_total,
        items=items,
    )


@router.get("/export.csv")
async def export_journal_csv(
    client_company_id: int = Query(...),
    from_date: date = Query(...),
    to_date: date = Query(...),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> StreamingResponse:
    """회계프로그램(더존·세무사랑) import용 일반전표 CSV 다운로드."""
    entries = await _collect_entries(db, current_user, client_company_id, from_date, to_date)
    csv_text = _UTF8_BOM + journal_entries_to_csv(entries)

    filename = f"journal_{client_company_id}_{from_date}_{to_date}.csv"
    logger.info(
        "journal.export",
        tenant_id=current_user.tenant_id,
        client_company_id=client_company_id,
        entry_count=len(entries),
    )

    return StreamingResponse(
        iter([csv_text]),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}",
        },
    )
