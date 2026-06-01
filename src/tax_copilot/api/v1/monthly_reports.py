"""Monthly client settlement reports."""

from calendar import monthrange
from datetime import date
from html import escape

from fastapi import APIRouter, Depends, Query
from fastapi.responses import HTMLResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from tax_copilot.api.deps import CurrentUser, get_current_user, get_db
from tax_copilot.core.exceptions import AuthorizationError, ValidationError
from tax_copilot.infra.db.models.filing_deadline import DEADLINE_STATUS_COMPLETED, FilingDeadline
from tax_copilot.infra.db.models.receipt import STATUS_APPROVED, STATUS_NEEDS_REVIEW, Receipt
from tax_copilot.infra.db.models.tax_invoice import (
    INVOICE_DIRECTION_PURCHASE,
    INVOICE_DIRECTION_SALE,
    TaxInvoice,
)
from tax_copilot.infra.db.models.user import ROLE_CLIENT
from tax_copilot.schemas.monthly_reports import MonthlyReportResponse

router = APIRouter(prefix="/monthly-reports", tags=["monthly-reports"])


@router.get("", response_model=MonthlyReportResponse)
async def get_monthly_report(
    client_company_id: int = Query(...),
    month: str = Query(..., description="YYYY-MM"),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> MonthlyReportResponse:
    """Return monthly settlement metrics for receipts and tax invoices."""
    _authorize_company(current_user, client_company_id)
    from_date, to_date = _month_range(month)
    return await _build_report(
        db, current_user.tenant_id, client_company_id, month, from_date, to_date
    )


@router.get("/html", response_class=HTMLResponse)
async def download_monthly_report_html(
    client_company_id: int = Query(...),
    month: str = Query(..., description="YYYY-MM"),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> HTMLResponse:
    """Download a print-ready HTML report that can be saved as PDF."""
    _authorize_company(current_user, client_company_id)
    from_date, to_date = _month_range(month)
    report = await _build_report(
        db, current_user.tenant_id, client_company_id, month, from_date, to_date
    )
    html = _render_report_html(report)
    return HTMLResponse(
        content=html,
        headers={"Content-Disposition": f'attachment; filename="monthly-report-{month}.html"'},
    )


async def _build_report(
    db: AsyncSession,
    tenant_id: int,
    client_company_id: int,
    month: str,
    from_date: date,
    to_date: date,
) -> MonthlyReportResponse:
    receipt_result = await db.execute(
        select(Receipt).where(
            Receipt.tenant_id == tenant_id,
            Receipt.client_company_id == client_company_id,
            Receipt.transaction_date >= from_date,
            Receipt.transaction_date <= to_date,
            Receipt.status.in_([STATUS_APPROVED, STATUS_NEEDS_REVIEW]),
        )
    )
    receipts = receipt_result.scalars().all()
    invoice_result = await db.execute(
        select(TaxInvoice).where(
            TaxInvoice.tenant_id == tenant_id,
            TaxInvoice.client_company_id == client_company_id,
            TaxInvoice.issue_date >= from_date,
            TaxInvoice.issue_date <= to_date,
        )
    )
    invoices = invoice_result.scalars().all()
    deadline_result = await db.execute(
        select(FilingDeadline)
        .where(
            FilingDeadline.tenant_id == tenant_id,
            FilingDeadline.client_company_id == client_company_id,
            FilingDeadline.due_date >= to_date,
            FilingDeadline.status != DEADLINE_STATUS_COMPLETED,
        )
        .order_by(FilingDeadline.due_date.asc())
    )
    next_deadline = deadline_result.scalars().first()

    approved_receipts = [r for r in receipts if r.status == STATUS_APPROVED]
    pending_receipts = [r for r in receipts if r.status == STATUS_NEEDS_REVIEW]
    receipt_input_vat = sum(_receipt_vat(r) for r in approved_receipts)
    purchase_invoices = [i for i in invoices if i.direction == INVOICE_DIRECTION_PURCHASE]
    sales_invoices = [i for i in invoices if i.direction == INVOICE_DIRECTION_SALE]
    purchase_invoice_vat = sum(i.vat_krw for i in purchase_invoices)
    sales_invoice_vat = sum(i.vat_krw for i in sales_invoices)
    total_input_vat = receipt_input_vat + purchase_invoice_vat

    return MonthlyReportResponse(
        client_company_id=client_company_id,
        month=month,
        from_date=from_date,
        to_date=to_date,
        processed_receipt_count=len(approved_receipts),
        pending_receipt_count=len(pending_receipts),
        purchase_invoice_count=len(purchase_invoices),
        sales_invoice_count=len(sales_invoices),
        receipt_input_vat_krw=receipt_input_vat,
        purchase_invoice_vat_krw=purchase_invoice_vat,
        sales_invoice_vat_krw=sales_invoice_vat,
        total_input_vat_krw=total_input_vat,
        estimated_vat_payable_krw=sales_invoice_vat - total_input_vat,
        next_deadline=None
        if next_deadline is None
        else {
            "id": next_deadline.id,
            "tax_type": next_deadline.tax_type,
            "due_date": next_deadline.due_date.isoformat(),
            "description": next_deadline.description,
        },
    )


def _receipt_vat(receipt: Receipt) -> int:
    parsed = receipt.parsed_data or {}
    if parsed.get("vat_creditable") is not True:
        return 0
    calc = parsed.get("calculation_result") or {}
    return int(calc.get("vat_krw") or 0)


def _month_range(month: str) -> tuple[date, date]:
    try:
        year, month_num = (int(part) for part in month.split("-", 1))
        return date(year, month_num, 1), date(year, month_num, monthrange(year, month_num)[1])
    except Exception as exc:
        raise ValidationError("month는 YYYY-MM 형식이어야 합니다.") from exc


def _authorize_company(current_user: CurrentUser, client_company_id: int) -> None:
    if current_user.role != ROLE_CLIENT:
        return
    if current_user.client_company_id is None:
        raise AuthorizationError("client 계정에 고객사가 연결되어 있지 않습니다.")
    if client_company_id != current_user.client_company_id:
        raise AuthorizationError("다른 고객사의 월별 리포트에 접근할 수 없습니다.")


def _render_report_html(report: MonthlyReportResponse) -> str:
    deadline = report.next_deadline
    deadline_text = (
        f"{escape(str(deadline['due_date']))} / {escape(str(deadline['description']))}"
        if deadline
        else "예정된 신고 기한 없음"
    )
    money = {
        "receipt_input": f"{report.receipt_input_vat_krw:,}",
        "purchase_input": f"{report.purchase_invoice_vat_krw:,}",
        "sales": f"{report.sales_invoice_vat_krw:,}",
        "total_input": f"{report.total_input_vat_krw:,}",
        "payable": f"{report.estimated_vat_payable_krw:,}",
    }
    return f"""<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8" />
  <title>{escape(report.month)} 월별 마감 리포트</title>
  <style>
    body {{ font-family: Arial, sans-serif; color: #172033; margin: 40px; }}
    h1 {{ margin-bottom: 6px; }}
    .muted {{ color: #61708a; }}
    .grid {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; margin: 24px 0; }}
    .card {{ border: 1px solid #d8e0ea; border-radius: 8px; padding: 16px; }}
    .card strong {{ display: block; font-size: 24px; margin-top: 8px; }}
    table {{ border-collapse: collapse; width: 100%; margin-top: 20px; }}
    th, td {{ border-bottom: 1px solid #d8e0ea; padding: 10px; text-align: right; }}
    th:first-child, td:first-child {{ text-align: left; }}
  </style>
</head>
<body>
  <h1>{escape(report.month)} 월별 마감 리포트</h1>
  <p class="muted">기간: {report.from_date.isoformat()} - {report.to_date.isoformat()}</p>
  <div class="grid">
    <div class="card">처리된 영수증<strong>{report.processed_receipt_count:,}건</strong></div>
    <div class="card">매입 세금계산서<strong>{report.purchase_invoice_count:,}건</strong></div>
    <div class="card">매출 세금계산서<strong>{report.sales_invoice_count:,}건</strong></div>
  </div>
  <table>
    <tr><th>항목</th><th>금액</th></tr>
    <tr><td>영수증 매입세액</td><td>{money["receipt_input"]}원</td></tr>
    <tr><td>세금계산서 매입세액</td><td>{money["purchase_input"]}원</td></tr>
    <tr><td>매입세액 합계</td><td>{money["total_input"]}원</td></tr>
    <tr><td>매출세액</td><td>{money["sales"]}원</td></tr>
    <tr><td>예상 납부세액</td><td>{money["payable"]}원</td></tr>
  </table>
  <p><strong>다음 신고 기한:</strong> {deadline_text}</p>
</body>
</html>"""
