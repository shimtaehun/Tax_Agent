"""SSE 실시간 처리 상태 알림 테스트."""

import pytest


@pytest.mark.anyio
class TestReceiptSSE:
    """GET /api/v1/receipts/{receipt_id}/events SSE 엔드포인트."""

    async def test_requires_auth(self, async_client) -> None:  # type: ignore[no-untyped-def]
        resp = await async_client.get("/api/v1/receipts/1/events")
        assert resp.status_code == 401

    async def test_sse_streams_status_events(self, auth_headers) -> None:  # type: ignore[no-untyped-def]
        """영수증이 즉시 APPROVED 상태 → data 이벤트 + done 이벤트 스트림."""
        from unittest.mock import MagicMock, patch

        from httpx import ASGITransport, AsyncClient

        from tax_copilot.api.deps import get_current_user
        from tax_copilot.api.main import app
        from tax_copilot.infra.db.models.receipt import Receipt

        mock_receipt = MagicMock(spec=Receipt)
        mock_receipt.id = 1
        mock_receipt.tenant_id = 1
        mock_receipt.status = "APPROVED"

        async def mock_get_current_user_override():
            from tax_copilot.api.deps import CurrentUser

            return CurrentUser(user_id=1, tenant_id=1, role="staff")

        from unittest.mock import AsyncMock

        mock_db = AsyncMock()
        mock_db.get = AsyncMock(return_value=mock_receipt)

        with patch("tax_copilot.api.v1.receipts.AsyncSessionLocal") as mock_session_factory:
            mock_cm = MagicMock()
            mock_cm.__aenter__ = AsyncMock(return_value=mock_db)
            mock_cm.__aexit__ = AsyncMock(return_value=False)
            mock_session_factory.return_value = mock_cm

            app.dependency_overrides[get_current_user] = mock_get_current_user_override
            try:
                async with AsyncClient(
                    transport=ASGITransport(app=app), base_url="http://test"
                ) as client:
                    resp = await client.get(
                        "/api/v1/receipts/1/events",
                        headers=auth_headers,
                    )
            finally:
                app.dependency_overrides.pop(get_current_user, None)

        assert resp.status_code == 200
        assert "text/event-stream" in resp.headers["content-type"]
        body = resp.text
        assert "data:" in body
        assert "APPROVED" in body

    async def test_unknown_receipt_closes_stream(self, auth_headers) -> None:  # type: ignore[no-untyped-def]
        """존재하지 않는 영수증 → 빈 스트림 종료."""
        from unittest.mock import MagicMock, patch

        from httpx import ASGITransport, AsyncClient

        from tax_copilot.api.deps import get_current_user
        from tax_copilot.api.main import app

        async def mock_get_current_user_override():
            from tax_copilot.api.deps import CurrentUser

            return CurrentUser(user_id=1, tenant_id=1, role="staff")

        from unittest.mock import AsyncMock

        mock_db = AsyncMock()
        mock_db.get = AsyncMock(return_value=None)

        with patch("tax_copilot.api.v1.receipts.AsyncSessionLocal") as mock_session_factory:
            mock_cm = MagicMock()
            mock_cm.__aenter__ = AsyncMock(return_value=mock_db)
            mock_cm.__aexit__ = AsyncMock(return_value=False)
            mock_session_factory.return_value = mock_cm

            app.dependency_overrides[get_current_user] = mock_get_current_user_override
            try:
                async with AsyncClient(
                    transport=ASGITransport(app=app), base_url="http://test"
                ) as client:
                    resp = await client.get(
                        "/api/v1/receipts/999/events",
                        headers=auth_headers,
                    )
            finally:
                app.dependency_overrides.pop(get_current_user, None)

        assert resp.status_code == 200
        assert "text/event-stream" in resp.headers["content-type"]
