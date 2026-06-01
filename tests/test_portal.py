"""고객사 포털 대시보드 테스트."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from tax_copilot.api.deps import get_db
from tax_copilot.api.main import app
from tax_copilot.auth.jwt import create_access_token
from tax_copilot.infra.db.models.receipt import Receipt


def _client_headers(client_company_id: int) -> dict[str, str]:
    token = create_access_token(
        user_id=10, tenant_id=1, role="client", client_company_id=client_company_id
    )
    return {"Authorization": f"Bearer {token}"}


def _staff_headers() -> dict[str, str]:
    token = create_access_token(user_id=1, tenant_id=1, role="staff")
    return {"Authorization": f"Bearer {token}"}


def _make_receipt(receipt_id: int, status: str, company_id: int) -> MagicMock:
    r = MagicMock(spec=Receipt)
    r.id = receipt_id
    r.tenant_id = 1
    r.client_company_id = company_id
    r.status = status
    r.original_filename = "invoice.pdf"
    r.mime_type = "application/pdf"
    r.file_size_bytes = 1024
    r.uploaded_by = 10
    r.transaction_date = None
    r.parsed_data = None
    r.langgraph_thread_id = None
    r.attempt_number = 1
    r.error_message = None
    r.reviewed_by = None
    r.reviewed_at = None
    r.review_comment = None
    r.account_code = None
    r.duplicate_suspect = False
    r.duplicate_receipt_ids = []
    _now = datetime.now(UTC)
    r.created_at = _now
    r.updated_at = _now
    return r


@pytest.mark.anyio
class TestPortalDashboard:
    async def test_client_gets_dashboard(self) -> None:
        """client 역할은 대시보드 조회 성공."""
        recent = [_make_receipt(i, "APPROVED", 42) for i in range(1, 4)]

        # 첫 번째 execute: status 집계, 두 번째 execute: 최근 5건
        count_row_1 = MagicMock()
        count_row_1.status = "APPROVED"
        count_row_1.cnt = 3
        count_result = MagicMock()
        count_result.__iter__ = MagicMock(return_value=iter([count_row_1]))

        scalars_mock = MagicMock()
        scalars_mock.all.return_value = recent
        recent_result = MagicMock()
        recent_result.scalars.return_value = scalars_mock

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(side_effect=[count_result, recent_result])

        async def override_get_db():
            yield mock_db

        app.dependency_overrides[get_db] = override_get_db
        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
                resp = await c.get("/api/v1/portal/dashboard", headers=_client_headers(42))
        finally:
            app.dependency_overrides.pop(get_db, None)

        assert resp.status_code == 200
        data = resp.json()
        assert data["client_company_id"] == 42
        assert data["total"] == 3
        assert data["by_status"] == {"APPROVED": 3}
        assert len(data["recent_receipts"]) == 3

    async def test_staff_cannot_access_dashboard(self) -> None:
        """staff 역할은 포털 대시보드 접근 불가 (403)."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.get("/api/v1/portal/dashboard", headers=_staff_headers())
        assert resp.status_code == 403

    async def test_unauthenticated_rejected(self) -> None:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.get("/api/v1/portal/dashboard")
        assert resp.status_code == 401
