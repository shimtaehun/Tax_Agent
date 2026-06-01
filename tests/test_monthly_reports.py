"""Monthly report endpoint tests."""

from datetime import date
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from tax_copilot.api.deps import get_db
from tax_copilot.api.main import app
from tax_copilot.auth.jwt import create_access_token


def _staff_headers() -> dict[str, str]:
    token = create_access_token(user_id=1, tenant_id=1, role="staff")
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.anyio
async def test_monthly_report_combines_receipts_and_invoices() -> None:
    receipt = MagicMock()
    receipt.status = "APPROVED"
    receipt.parsed_data = {
        "vat_creditable": True,
        "calculation_result": {"vat_krw": 1000},
    }
    purchase_invoice = MagicMock()
    purchase_invoice.direction = "PURCHASE"
    purchase_invoice.vat_krw = 2000
    sales_invoice = MagicMock()
    sales_invoice.direction = "SALE"
    sales_invoice.vat_krw = 5000

    receipt_scalars = MagicMock()
    receipt_scalars.all.return_value = [receipt]
    receipt_result = MagicMock()
    receipt_result.scalars.return_value = receipt_scalars

    invoice_scalars = MagicMock()
    invoice_scalars.all.return_value = [purchase_invoice, sales_invoice]
    invoice_result = MagicMock()
    invoice_result.scalars.return_value = invoice_scalars

    deadline = MagicMock()
    deadline.id = 3
    deadline.tax_type = "vat"
    deadline.due_date = date(2026, 7, 25)
    deadline.description = "부가세 예정신고"
    deadline_scalars = MagicMock()
    deadline_scalars.first.return_value = deadline
    deadline_result = MagicMock()
    deadline_result.scalars.return_value = deadline_scalars

    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(side_effect=[receipt_result, invoice_result, deadline_result])

    async def override_get_db():
        yield mock_db

    app.dependency_overrides[get_db] = override_get_db
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get(
                "/api/v1/monthly-reports",
                params={"client_company_id": 1, "month": "2026-05"},
                headers=_staff_headers(),
            )
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert resp.status_code == 200
    data = resp.json()
    assert data["processed_receipt_count"] == 1
    assert data["purchase_invoice_vat_krw"] == 2000
    assert data["sales_invoice_vat_krw"] == 5000
    assert data["total_input_vat_krw"] == 3000
    assert data["estimated_vat_payable_krw"] == 2000
