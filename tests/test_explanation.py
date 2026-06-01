"""판단 근거 추적성 테스트."""

import pytest


@pytest.mark.anyio
class TestExplanationEndpoint:
    """GET /api/v1/receipts/{id}/explanation."""

    async def test_requires_auth(self, async_client) -> None:  # type: ignore[no-untyped-def]
        resp = await async_client.get("/api/v1/receipts/1/explanation")
        assert resp.status_code == 401

    async def test_returns_explanation_structure(self, auth_headers) -> None:  # type: ignore[no-untyped-def]
        from unittest.mock import AsyncMock, MagicMock

        from httpx import ASGITransport, AsyncClient

        from tax_copilot.api.deps import get_db
        from tax_copilot.api.main import app
        from tax_copilot.infra.db.models.receipt import Receipt

        mock_receipt = MagicMock(spec=Receipt)
        mock_receipt.id = 1
        mock_receipt.tenant_id = 1
        mock_receipt.status = "APPROVED"
        mock_receipt.account_code = "복리후생비"
        mock_receipt.parsed_data = {
            "vat_creditable": True,
            "expense_deductible": True,
            "account_code": "복리후생비",
            "account_code_reason": "카페 키워드 매칭",
            "evidence_type": "credit_card_slip",
            "evidence_status": "valid",
            "confidence": 0.92,
            "risk_flags": [],
            "citations": [
                {
                    "chunk_id": "c1",
                    "law_name": "부가가치세법",
                    "article_no": "제38조",
                    "paragraph_no": "제1항",
                    "effective_from": "2024-01-01",
                    "effective_to": None,
                    "quoted_text": "매입세액은 공제한다.",
                }
            ],
            "prompt_version": "v0.3-rule-based",
            "model_name": "gemini-2.0-flash",
            "law_corpus_version": "v1",
            "calculation_result": {"supply_value_krw": 5000, "vat_krw": 500, "total_krw": 5500},
            "human_approved": None,
            "human_comment": None,
        }

        mock_scalars = MagicMock()
        mock_scalars.all.return_value = []
        first_result = MagicMock()
        first_result.scalar_one_or_none.return_value = mock_receipt
        second_result = MagicMock()
        second_result.scalars.return_value = mock_scalars
        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(side_effect=[first_result, second_result])

        async def override_get_db():
            yield mock_db

        app.dependency_overrides[get_db] = override_get_db
        try:
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                resp = await client.get("/api/v1/receipts/1/explanation", headers=auth_headers)
        finally:
            app.dependency_overrides.pop(get_db, None)

        assert resp.status_code == 200
        data = resp.json()
        assert "receipt_id" in data
        assert "decision" in data
        assert "citations" in data
        assert "risk_flags" in data
        assert "audit_trail" in data

    async def test_not_found_returns_404(self, auth_headers) -> None:  # type: ignore[no-untyped-def]
        from unittest.mock import AsyncMock, MagicMock

        from httpx import ASGITransport, AsyncClient

        from tax_copilot.api.deps import get_db
        from tax_copilot.api.main import app

        not_found_result = MagicMock()
        not_found_result.scalar_one_or_none.return_value = None
        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=not_found_result)

        async def override_get_db():
            yield mock_db

        app.dependency_overrides[get_db] = override_get_db
        try:
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                resp = await client.get("/api/v1/receipts/999/explanation", headers=auth_headers)
        finally:
            app.dependency_overrides.pop(get_db, None)

        assert resp.status_code == 404

    async def test_pending_receipt_returns_no_decision(self, auth_headers) -> None:  # type: ignore[no-untyped-def]
        """아직 처리 중인 영수증 → decision 없음."""
        from unittest.mock import AsyncMock, MagicMock

        from httpx import ASGITransport, AsyncClient

        from tax_copilot.api.deps import get_db
        from tax_copilot.api.main import app
        from tax_copilot.infra.db.models.receipt import Receipt

        mock_receipt = MagicMock(spec=Receipt)
        mock_receipt.id = 2
        mock_receipt.tenant_id = 1
        mock_receipt.status = "PENDING"
        mock_receipt.parsed_data = None

        mock_scalars = MagicMock()
        mock_scalars.all.return_value = []
        first_result = MagicMock()
        first_result.scalar_one_or_none.return_value = mock_receipt
        second_result = MagicMock()
        second_result.scalars.return_value = mock_scalars
        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(side_effect=[first_result, second_result])

        async def override_get_db():
            yield mock_db

        app.dependency_overrides[get_db] = override_get_db
        try:
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                resp = await client.get("/api/v1/receipts/2/explanation", headers=auth_headers)
        finally:
            app.dependency_overrides.pop(get_db, None)

        assert resp.status_code == 200
        data = resp.json()
        assert data["decision"] is None
        assert data["citations"] == []

    async def test_client_cannot_access_other_company_explanation(self) -> None:
        """client는 같은 tenant라도 다른 고객사 영수증 판단 근거를 볼 수 없다."""
        from unittest.mock import AsyncMock, MagicMock

        from httpx import ASGITransport, AsyncClient

        from tax_copilot.api.deps import get_db
        from tax_copilot.api.main import app
        from tax_copilot.auth.jwt import create_access_token
        from tax_copilot.infra.db.models.receipt import Receipt

        mock_receipt = MagicMock(spec=Receipt)
        mock_receipt.id = 3
        mock_receipt.tenant_id = 1
        mock_receipt.client_company_id = 99

        found_result = MagicMock()
        found_result.scalar_one_or_none.return_value = mock_receipt
        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=found_result)

        async def override_get_db():
            yield mock_db

        token = create_access_token(user_id=10, tenant_id=1, role="client", client_company_id=42)
        app.dependency_overrides[get_db] = override_get_db
        try:
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                resp = await client.get(
                    "/api/v1/receipts/3/explanation",
                    headers={"Authorization": f"Bearer {token}"},
                )
        finally:
            app.dependency_overrides.pop(get_db, None)

        assert resp.status_code == 400
