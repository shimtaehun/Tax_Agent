"""HITL review API tests."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from tax_copilot.api.deps import get_db
from tax_copilot.api.main import app
from tax_copilot.auth.jwt import create_access_token
from tax_copilot.infra.db.models.receipt import Receipt


def _staff_headers() -> dict[str, str]:
    token = create_access_token(user_id=1, tenant_id=1, role="staff")
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.anyio
async def test_decide_persists_human_decision_into_draft() -> None:
    """승인/반려 결과를 저장된 검토 초안에 병합한다."""
    receipt = MagicMock(spec=Receipt)
    receipt.id = 7
    receipt.tenant_id = 1
    receipt.status = "NEEDS_REVIEW"
    receipt.langgraph_thread_id = "thread-7"
    receipt.parsed_data = {
        "account_code": "복리후생비",
        "requires_human_review": True,
        "human_approved": None,
        "human_comment": None,
    }
    receipt.account_code = "복리후생비"
    receipt.transaction_date = None
    receipt.reviewed_by = None
    receipt.reviewed_at = None
    receipt.review_comment = None
    receipt.updated_at = datetime.now(UTC)

    found_result = MagicMock()
    found_result.scalar_one_or_none.return_value = receipt
    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(return_value=found_result)
    mock_db.flush = AsyncMock()
    mock_db.commit = AsyncMock()
    mock_db.add = MagicMock()

    async def override_get_db():
        yield mock_db

    app.dependency_overrides[get_db] = override_get_db
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post(
                "/api/v1/reviews/7/decide",
                headers=_staff_headers(),
                json={"approved": True, "comment": "확인 완료"},
            )
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert resp.status_code == 200
    assert receipt.status == "APPROVED"
    assert receipt.parsed_data["human_approved"] is True
    assert receipt.parsed_data["human_comment"] == "확인 완료"
    assert receipt.parsed_data["requires_human_review"] is False
    assert receipt.account_code == "복리후생비"
