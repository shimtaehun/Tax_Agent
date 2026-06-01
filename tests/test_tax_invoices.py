"""Tax invoice import tests."""

from datetime import date, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from tax_copilot.api.deps import get_db
from tax_copilot.api.main import app
from tax_copilot.auth.jwt import create_access_token
from tax_copilot.core.tax.invoice_parser import parse_tax_invoice_file
from tax_copilot.infra.db.models.tax_invoice import TaxInvoice


def _staff_headers() -> dict[str, str]:
    token = create_access_token(user_id=1, tenant_id=1, role="staff")
    return {"Authorization": f"Bearer {token}"}


def _invoice() -> MagicMock:
    invoice = MagicMock(spec=TaxInvoice)
    invoice.id = 1
    invoice.tenant_id = 1
    invoice.client_company_id = 1
    invoice.direction = "PURCHASE"
    invoice.approval_no = "A1"
    invoice.issue_date = date(2026, 5, 2)
    invoice.supplier_business_no = "111"
    invoice.supplier_name = "공급상사"
    invoice.recipient_business_no = "222"
    invoice.recipient_name = "고객회사"
    invoice.item_name = "서비스"
    invoice.supply_value_krw = 1000
    invoice.vat_krw = 100
    invoice.total_amount_krw = 1100
    invoice.source_filename = "invoices.csv"
    invoice.created_at = datetime(2026, 5, 2)
    return invoice


def test_parse_hometax_csv() -> None:
    content = (
        "구분,승인번호,작성일자,공급자상호,공급받는자상호,품목명,공급가액,세액,합계금액\n"
        '매입,ABC-1,2026-05-10,공급상사,고객회사,자문료,"100,000","10,000","110,000"\n'
    ).encode("utf-8-sig")

    rows = parse_tax_invoice_file("hometax.csv", content)

    assert len(rows) == 1
    assert rows[0].direction == "PURCHASE"
    assert rows[0].approval_no == "ABC-1"
    assert rows[0].issue_date == date(2026, 5, 10)
    assert rows[0].vat_krw == 10_000


@pytest.mark.anyio
async def test_upload_tax_invoice_csv_imports_rows() -> None:
    existing_result = MagicMock()
    existing_result.scalar_one_or_none.return_value = None
    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(return_value=existing_result)
    mock_db.flush = AsyncMock()
    mock_db.commit = AsyncMock()
    mock_db.refresh = AsyncMock()

    def add_row(row: TaxInvoice) -> None:
        row.id = 1
        row.created_at = datetime(2026, 5, 1)

    mock_db.add = MagicMock(side_effect=add_row)

    async def override_get_db():
        yield mock_db

    app.dependency_overrides[get_db] = override_get_db
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post(
                "/api/v1/tax-invoices/upload",
                params={"client_company_id": 1, "invoice_direction": "PURCHASE"},
                files={
                    "file": (
                        "invoices.csv",
                        "승인번호,작성일자,공급자상호,공급가액,세액\nA1,2026-05-01,공급상사,1000,100\n",
                        "text/csv",
                    )
                },
                headers=_staff_headers(),
            )
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert resp.status_code == 201
    assert resp.json()["imported_count"] == 1
    assert mock_db.add.called


@pytest.mark.anyio
async def test_list_tax_invoices_returns_items() -> None:
    invoice = _invoice()
    invoice.direction = "SALE"
    invoice.approval_no = "S1"
    invoice.supplier_name = "우리회사"
    invoice.recipient_name = "거래처"
    invoice.source_filename = "sales.csv"

    count_result = MagicMock()
    count_result.scalar_one.return_value = 1
    scalars = MagicMock()
    scalars.all.return_value = [invoice]
    list_result = MagicMock()
    list_result.scalars.return_value = scalars
    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(side_effect=[count_result, list_result])

    async def override_get_db():
        yield mock_db

    app.dependency_overrides[get_db] = override_get_db
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get(
                "/api/v1/tax-invoices",
                params={"client_company_id": 1},
                headers=_staff_headers(),
            )
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert resp.status_code == 200
    assert resp.json()["total"] == 1
    assert resp.json()["items"][0]["approval_no"] == "S1"


@pytest.mark.anyio
async def test_update_tax_invoice_changes_reviewed_fields() -> None:
    invoice = _invoice()
    found_result = MagicMock()
    found_result.scalar_one_or_none.return_value = invoice
    duplicate_result = MagicMock()
    duplicate_result.scalar_one_or_none.return_value = None
    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(side_effect=[found_result, duplicate_result])
    mock_db.commit = AsyncMock()
    mock_db.refresh = AsyncMock()

    async def override_get_db():
        yield mock_db

    app.dependency_overrides[get_db] = override_get_db
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.patch(
                "/api/v1/tax-invoices/1",
                headers=_staff_headers(),
                json={
                    "approval_no": "A1-EDIT",
                    "item_name": "수정 품목",
                    "supply_value_krw": 2000,
                    "vat_krw": 200,
                    "total_amount_krw": 2200,
                },
            )
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert resp.status_code == 200
    assert invoice.approval_no == "A1-EDIT"
    assert invoice.item_name == "수정 품목"
    assert invoice.vat_krw == 200
    assert resp.json()["total_amount_krw"] == 2200


@pytest.mark.anyio
async def test_delete_tax_invoice_deletes_row() -> None:
    invoice = _invoice()
    found_result = MagicMock()
    found_result.scalar_one_or_none.return_value = invoice
    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(return_value=found_result)
    mock_db.delete = AsyncMock()
    mock_db.commit = AsyncMock()

    async def override_get_db():
        yield mock_db

    app.dependency_overrides[get_db] = override_get_db
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.delete("/api/v1/tax-invoices/1", headers=_staff_headers())
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert resp.status_code == 204
    mock_db.delete.assert_awaited_once_with(invoice)
