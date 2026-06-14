"""카드사 결제내역 업로드 API 테스트."""

from datetime import date, datetime, time
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from tax_copilot.api.deps import get_db
from tax_copilot.api.main import app
from tax_copilot.auth.jwt import create_access_token
from tax_copilot.infra.db.models.card_transaction import CardTransaction

_FIXTURE = Path(__file__).parent / "fixtures" / "statements" / "hyundai_sample.xls"


def _staff_headers() -> dict[str, str]:
    token = create_access_token(user_id=1, tenant_id=1, role="staff")
    return {"Authorization": f"Bearer {token}"}


def _client_headers(client_company_id: int) -> dict[str, str]:
    token = create_access_token(
        user_id=2, tenant_id=1, role="client", client_company_id=client_company_id
    )
    return {"Authorization": f"Bearer {token}"}


def _mock_db_no_duplicates() -> AsyncMock:
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    db = AsyncMock()
    db.execute = AsyncMock(return_value=result)
    db.add = MagicMock()
    db.commit = AsyncMock()
    return db


@pytest.mark.anyio
async def test_upload_hyundai_statement_imports_rows() -> None:
    mock_db = _mock_db_no_duplicates()

    async def override_get_db():
        yield mock_db

    app.dependency_overrides[get_db] = override_get_db
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post(
                "/api/v1/statements/upload",
                params={"client_company_id": 1, "card_company": "hyundai"},
                files={
                    "file": (
                        "hyundaicard_20260611.xls",
                        _FIXTURE.read_bytes(),
                        "application/vnd.ms-excel",
                    )
                },
                headers=_staff_headers(),
            )
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert resp.status_code == 201
    body = resp.json()
    assert body["imported_count"] == 2
    assert body["skipped_count"] == 0
    assert body["card_company"] == "hyundai"
    assert mock_db.add.call_count == 2


@pytest.mark.anyio
async def test_upload_autodetects_card_company_from_filename() -> None:
    mock_db = _mock_db_no_duplicates()

    async def override_get_db():
        yield mock_db

    app.dependency_overrides[get_db] = override_get_db
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post(
                "/api/v1/statements/upload",
                params={"client_company_id": 1},  # card_company 미지정 → 파일명으로 자동 판별
                files={
                    "file": (
                        "hyundaicard_20260611.xls",
                        _FIXTURE.read_bytes(),
                        "application/vnd.ms-excel",
                    )
                },
                headers=_staff_headers(),
            )
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert resp.status_code == 201
    assert resp.json()["card_company"] == "hyundai"


@pytest.mark.anyio
async def test_upload_unknown_card_company_returns_400() -> None:
    mock_db = _mock_db_no_duplicates()

    async def override_get_db():
        yield mock_db

    app.dependency_overrides[get_db] = override_get_db
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post(
                "/api/v1/statements/upload",
                params={"client_company_id": 1, "card_company": "nonexistent_card"},
                files={
                    "file": (
                        "mystery.xls",
                        _FIXTURE.read_bytes(),
                        "application/vnd.ms-excel",
                    )
                },
                headers=_staff_headers(),
            )
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert resp.status_code == 400


# --- 목록 조회 (GET /statements) -------------------------------------------


def _txn() -> MagicMock:
    txn = MagicMock(spec=CardTransaction)
    txn.id = 10
    txn.client_company_id = 1
    txn.card_company = "hyundai"
    txn.transaction_date = date(2026, 6, 11)
    txn.transaction_time = time(11, 57)
    txn.merchant_name = "공간의미"
    txn.approval_no = "00688404"
    txn.card_no_masked = "4***-****-****-130*"
    txn.total_amount_krw = 7_500
    txn.installment_months = 0
    txn.account_code = "복리후생비"
    txn.cancelled = False
    txn.status = "PENDING"
    txn.source_filename = "hyundaicard_20260611.xls"
    txn.created_at = datetime(2026, 6, 11, 12, 0)
    return txn


def _mock_db_list(items: list[MagicMock], total: int) -> AsyncMock:
    count_result = MagicMock()
    count_result.scalar_one.return_value = total
    scalars = MagicMock()
    scalars.all.return_value = items
    list_result = MagicMock()
    list_result.scalars.return_value = scalars
    db = AsyncMock()
    db.execute = AsyncMock(side_effect=[count_result, list_result])
    return db


@pytest.mark.anyio
async def test_list_statements_returns_items() -> None:
    mock_db = _mock_db_list([_txn()], total=1)

    async def override_get_db():
        yield mock_db

    app.dependency_overrides[get_db] = override_get_db
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get(
                "/api/v1/statements",
                params={"client_company_id": 1},
                headers=_staff_headers(),
            )
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert body["items"][0]["approval_no"] == "00688404"
    assert body["items"][0]["card_company"] == "hyundai"
    assert body["items"][0]["total_amount_krw"] == 7_500


@pytest.mark.anyio
async def test_list_statements_client_cannot_access_other_company() -> None:
    mock_db = _mock_db_list([], total=0)

    async def override_get_db():
        yield mock_db

    app.dependency_overrides[get_db] = override_get_db
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get(
                "/api/v1/statements",
                params={"client_company_id": 1},  # client 계정은 회사 5 소속
                headers=_client_headers(5),
            )
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert resp.status_code == 403


@pytest.mark.anyio
async def test_upload_undetectable_card_company_returns_400() -> None:
    mock_db = _mock_db_no_duplicates()

    async def override_get_db():
        yield mock_db

    app.dependency_overrides[get_db] = override_get_db
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post(
                "/api/v1/statements/upload",
                params={"client_company_id": 1},  # 미지정 + 파일명으로도 판별 불가
                files={
                    "file": (
                        "mystery.xls",
                        _FIXTURE.read_bytes(),
                        "application/vnd.ms-excel",
                    )
                },
                headers=_staff_headers(),
            )
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert resp.status_code == 400
