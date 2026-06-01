"""Receipt operational endpoint tests."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from tax_copilot.api.deps import get_db
from tax_copilot.api.main import app
from tax_copilot.auth.jwt import create_access_token
from tax_copilot.infra.db.models.audit_event import AuditEvent
from tax_copilot.infra.db.models.receipt import Receipt


def _staff_headers() -> dict[str, str]:
    token = create_access_token(user_id=1, tenant_id=1, role="staff")
    return {"Authorization": f"Bearer {token}"}


def _receipt(status: str = "FAILED") -> MagicMock:
    r = MagicMock(spec=Receipt)
    r.id = 5
    r.tenant_id = 1
    r.client_company_id = 42
    r.uploaded_by = 1
    r.file_path = "/tmp/receipt.jpg"
    r.file_hash = "abc123"
    r.original_filename = "receipt.jpg"
    r.mime_type = "image/jpeg"
    r.file_size_bytes = 1000
    r.transaction_date = None
    r.parsed_data = None
    r.status = status
    r.langgraph_thread_id = "thread-5"
    r.celery_task_id = None
    r.attempt_number = 1
    r.error_message = "boom"
    r.reviewed_by = None
    r.reviewed_at = None
    r.review_comment = None
    r.account_code = None
    r.duplicate_suspect = False
    r.duplicate_receipt_ids = []
    r.created_at = datetime.now(UTC)
    r.updated_at = datetime.now(UTC)
    return r


@pytest.mark.anyio
async def test_retry_receipt_dispatches_task() -> None:
    receipt = _receipt()
    found = MagicMock()
    found.scalar_one_or_none.return_value = receipt
    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(return_value=found)
    mock_db.flush = AsyncMock()
    mock_db.commit = AsyncMock()
    mock_db.refresh = AsyncMock()
    mock_db.add = MagicMock()

    async def override_get_db():
        yield mock_db

    app.dependency_overrides[get_db] = override_get_db
    try:
        with patch("tax_copilot.api.v1.receipts.dispatch_receipt_task", return_value="task-5"):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
                resp = await c.post("/api/v1/receipts/5/retry", headers=_staff_headers())
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert resp.status_code == 200
    assert receipt.status == "PENDING"
    assert receipt.attempt_number == 2


@pytest.mark.anyio
async def test_audit_csv_exports_events() -> None:
    receipt = _receipt(status="APPROVED")
    event = MagicMock(spec=AuditEvent)
    event.created_at = datetime(2026, 5, 30, tzinfo=UTC)
    event.event_type = "RECEIPT_UPLOADED"
    event.actor_user_id = 1
    event.payload = {"filename": "receipt.jpg"}

    found = MagicMock()
    found.scalar_one_or_none.return_value = receipt
    scalars = MagicMock()
    scalars.all.return_value = [event]
    events_result = MagicMock()
    events_result.scalars.return_value = scalars

    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(side_effect=[found, events_result])

    async def override_get_db():
        yield mock_db

    app.dependency_overrides[get_db] = override_get_db
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.get("/api/v1/receipts/5/audit.csv", headers=_staff_headers())
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert resp.status_code == 200
    assert "text/csv" in resp.headers["content-type"]
    assert "RECEIPT_UPLOADED" in resp.text
