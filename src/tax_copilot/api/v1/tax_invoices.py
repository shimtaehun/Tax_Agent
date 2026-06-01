"""Electronic tax invoice management API."""

from datetime import UTC, date, datetime

import structlog
from fastapi import APIRouter, Depends, Query, Response, UploadFile
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from tax_copilot.api.deps import CurrentUser, get_current_user, get_db
from tax_copilot.auth.permissions import require_staff_or_admin
from tax_copilot.core.exceptions import AuthorizationError, ValidationError
from tax_copilot.core.tax.invoice_parser import parse_tax_invoice_file
from tax_copilot.infra.db.models.tax_invoice import (
    INVOICE_DIRECTION_PURCHASE,
    INVOICE_DIRECTION_SALE,
    TaxInvoice,
)
from tax_copilot.infra.db.models.user import ROLE_CLIENT
from tax_copilot.schemas.tax_invoices import (
    TaxInvoiceItem,
    TaxInvoiceListResponse,
    TaxInvoiceUpdateRequest,
    TaxInvoiceUploadResponse,
)

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/tax-invoices", tags=["tax-invoices"])


def _to_item(invoice: TaxInvoice) -> TaxInvoiceItem:
    return TaxInvoiceItem(
        id=invoice.id,
        client_company_id=invoice.client_company_id,
        direction=invoice.direction,
        approval_no=invoice.approval_no,
        issue_date=invoice.issue_date,
        supplier_business_no=invoice.supplier_business_no,
        supplier_name=invoice.supplier_name,
        recipient_business_no=invoice.recipient_business_no,
        recipient_name=invoice.recipient_name,
        item_name=invoice.item_name,
        supply_value_krw=invoice.supply_value_krw,
        vat_krw=invoice.vat_krw,
        total_amount_krw=invoice.total_amount_krw,
        source_filename=invoice.source_filename,
        created_at=invoice.created_at,
    )


@router.get("", response_model=TaxInvoiceListResponse)
async def list_tax_invoices(
    client_company_id: int = Query(...),
    from_date: date | None = Query(default=None),
    to_date: date | None = Query(default=None),
    direction: str | None = Query(default=None),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> TaxInvoiceListResponse:
    """List imported sales/purchase electronic tax invoices."""
    _authorize_company(current_user, client_company_id)
    filters = [
        TaxInvoice.tenant_id == current_user.tenant_id,
        TaxInvoice.client_company_id == client_company_id,
    ]
    if from_date is not None:
        filters.append(TaxInvoice.issue_date >= from_date)
    if to_date is not None:
        filters.append(TaxInvoice.issue_date <= to_date)
    if direction is not None:
        filters.append(TaxInvoice.direction == direction)

    total_result = await db.execute(select(func.count()).select_from(TaxInvoice).where(*filters))
    result = await db.execute(
        select(TaxInvoice)
        .where(*filters)
        .order_by(TaxInvoice.issue_date.desc(), TaxInvoice.id.desc())
        .offset(skip)
        .limit(limit)
    )
    return TaxInvoiceListResponse(
        items=[_to_item(i) for i in result.scalars().all()],
        total=total_result.scalar_one(),
    )


@router.get("/{invoice_id}", response_model=TaxInvoiceItem)
async def get_tax_invoice(
    invoice_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> TaxInvoiceItem:
    """Return one imported tax invoice."""
    invoice = await _get_invoice_or_404(db, current_user, invoice_id)
    return _to_item(invoice)


@router.post("/upload", response_model=TaxInvoiceUploadResponse, status_code=201)
async def upload_tax_invoices(
    file: UploadFile,
    client_company_id: int = Query(...),
    invoice_direction: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> TaxInvoiceUploadResponse:
    """Import Hometax XML/CSV sales or purchase tax invoices."""
    require_staff_or_admin(current_user.role)
    if file.filename is None:
        from tax_copilot.core.exceptions import ValidationError

        raise ValidationError("파일명이 없습니다.")

    content = await file.read()
    parsed = parse_tax_invoice_file(file.filename, content, invoice_direction)
    imported: list[TaxInvoice] = []
    skipped = 0

    for item in parsed:
        existing = await db.execute(
            select(TaxInvoice.id).where(
                TaxInvoice.tenant_id == current_user.tenant_id,
                TaxInvoice.client_company_id == client_company_id,
                TaxInvoice.approval_no == item.approval_no,
            )
        )
        if existing.scalar_one_or_none() is not None:
            skipped += 1
            continue

        row = TaxInvoice(
            tenant_id=current_user.tenant_id,
            client_company_id=client_company_id,
            uploaded_by=current_user.user_id,
            direction=item.direction,
            approval_no=item.approval_no,
            issue_date=item.issue_date,
            supplier_business_no=item.supplier_business_no,
            supplier_name=item.supplier_name,
            recipient_business_no=item.recipient_business_no,
            recipient_name=item.recipient_name,
            item_name=item.item_name,
            supply_value_krw=item.supply_value_krw,
            vat_krw=item.vat_krw,
            total_amount_krw=item.total_amount_krw,
            source_filename=file.filename,
            raw_data=item.raw_data,
        )
        db.add(row)
        await db.flush()
        imported.append(row)

    await db.commit()
    for row in imported:
        await db.refresh(row)

    logger.info(
        "tax_invoices.imported",
        tenant_id=current_user.tenant_id,
        client_company_id=client_company_id,
        imported_count=len(imported),
        skipped_count=skipped,
    )
    return TaxInvoiceUploadResponse(
        imported_count=len(imported),
        skipped_count=skipped,
        items=[_to_item(i) for i in imported],
    )


@router.patch("/{invoice_id}", response_model=TaxInvoiceItem)
async def update_tax_invoice(
    invoice_id: int,
    body: TaxInvoiceUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> TaxInvoiceItem:
    """Update a manually reviewed tax invoice row."""
    require_staff_or_admin(current_user.role)
    invoice = await _get_invoice_or_404(db, current_user, invoice_id)

    if body.direction is not None:
        if body.direction not in {INVOICE_DIRECTION_SALE, INVOICE_DIRECTION_PURCHASE}:
            raise ValidationError("direction은 SALE 또는 PURCHASE이어야 합니다.")
        invoice.direction = body.direction
    if body.approval_no is not None:
        approval_no = body.approval_no.strip()
        if not approval_no:
            raise ValidationError("승인번호는 비워둘 수 없습니다.")
        existing = await db.execute(
            select(TaxInvoice.id).where(
                TaxInvoice.tenant_id == current_user.tenant_id,
                TaxInvoice.client_company_id == invoice.client_company_id,
                TaxInvoice.approval_no == approval_no,
                TaxInvoice.id != invoice.id,
            )
        )
        if existing.scalar_one_or_none() is not None:
            raise ValidationError("같은 승인번호의 세금계산서가 이미 있습니다.")
        invoice.approval_no = approval_no
    if body.issue_date is not None:
        invoice.issue_date = body.issue_date
    if body.supplier_business_no is not None:
        invoice.supplier_business_no = _clean_optional(body.supplier_business_no)
    if body.supplier_name is not None:
        invoice.supplier_name = _clean_optional(body.supplier_name)
    if body.recipient_business_no is not None:
        invoice.recipient_business_no = _clean_optional(body.recipient_business_no)
    if body.recipient_name is not None:
        invoice.recipient_name = _clean_optional(body.recipient_name)
    if body.item_name is not None:
        invoice.item_name = _clean_optional(body.item_name)
    if body.supply_value_krw is not None:
        invoice.supply_value_krw = _validate_amount(body.supply_value_krw, "공급가액")
    if body.vat_krw is not None:
        invoice.vat_krw = _validate_amount(body.vat_krw, "세액")
    if body.total_amount_krw is not None:
        invoice.total_amount_krw = _validate_amount(body.total_amount_krw, "합계금액")

    invoice.updated_at = datetime.now(UTC)
    await db.commit()
    await db.refresh(invoice)
    return _to_item(invoice)


@router.delete("/{invoice_id}", status_code=204)
async def delete_tax_invoice(
    invoice_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> Response:
    """Delete an imported tax invoice row."""
    require_staff_or_admin(current_user.role)
    invoice = await _get_invoice_or_404(db, current_user, invoice_id)
    await db.delete(invoice)
    await db.commit()
    return Response(status_code=204)


def _authorize_company(current_user: CurrentUser, client_company_id: int) -> None:
    if current_user.role != ROLE_CLIENT:
        return
    if current_user.client_company_id is None:
        raise AuthorizationError("client 계정에 고객사가 연결되어 있지 않습니다.")
    if client_company_id != current_user.client_company_id:
        raise AuthorizationError("다른 고객사의 세금계산서에 접근할 수 없습니다.")


async def _get_invoice_or_404(
    db: AsyncSession, current_user: CurrentUser, invoice_id: int
) -> TaxInvoice:
    filters = [
        TaxInvoice.id == invoice_id,
        TaxInvoice.tenant_id == current_user.tenant_id,
    ]
    if current_user.role == ROLE_CLIENT:
        if current_user.client_company_id is None:
            raise AuthorizationError("client 계정에 고객사가 연결되어 있지 않습니다.")
        filters.append(TaxInvoice.client_company_id == current_user.client_company_id)
    result = await db.execute(select(TaxInvoice).where(*filters))
    invoice = result.scalar_one_or_none()
    if invoice is None:
        raise ValidationError(f"세금계산서 {invoice_id}를 찾을 수 없습니다.")
    return invoice


def _clean_optional(value: str) -> str | None:
    cleaned = value.strip()
    return cleaned or None


def _validate_amount(value: int, label: str) -> int:
    if value < 0:
        raise ValidationError(f"{label}은 0 이상이어야 합니다.")
    return value
