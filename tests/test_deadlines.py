"""신고 기한 관리 테스트."""

import pytest


class TestDeadlineGeneration:
    """core/tax/deadlines.py — 순수 기한 계산 함수."""

    def test_generates_vat_deadlines_for_year(self) -> None:
        from tax_copilot.core.tax.deadlines import generate_annual_deadlines

        deadlines = generate_annual_deadlines(2026)
        tax_types = [d["tax_type"] for d in deadlines]
        assert "VAT_1기_예정" in tax_types
        assert "VAT_1기_확정" in tax_types
        assert "VAT_2기_예정" in tax_types
        assert "VAT_2기_확정" in tax_types

    def test_generates_income_and_corporate_tax(self) -> None:
        from tax_copilot.core.tax.deadlines import generate_annual_deadlines

        deadlines = generate_annual_deadlines(2026)
        tax_types = [d["tax_type"] for d in deadlines]
        assert "종합소득세" in tax_types
        assert "법인세" in tax_types

    def test_vat_1기_확정_due_date(self) -> None:
        """부가세 1기 확정 → 7월 25일."""
        from datetime import date

        from tax_copilot.core.tax.deadlines import generate_annual_deadlines

        deadlines = {d["tax_type"]: d for d in generate_annual_deadlines(2026)}
        assert deadlines["VAT_1기_확정"]["due_date"] == date(2026, 7, 25)

    def test_vat_2기_확정_due_next_year(self) -> None:
        """부가세 2기 확정 → 다음 해 1월 25일."""
        from datetime import date

        from tax_copilot.core.tax.deadlines import generate_annual_deadlines

        deadlines = {d["tax_type"]: d for d in generate_annual_deadlines(2026)}
        assert deadlines["VAT_2기_확정"]["due_date"] == date(2027, 1, 25)

    def test_deadline_has_required_fields(self) -> None:
        from tax_copilot.core.tax.deadlines import generate_annual_deadlines

        for d in generate_annual_deadlines(2026):
            assert "tax_type" in d
            assert "due_date" in d
            assert "fiscal_year" in d
            assert "description" in d


@pytest.mark.anyio
class TestDeadlineEndpoints:
    """GET/POST /api/v1/deadlines 엔드포인트."""

    async def test_requires_auth(self, async_client) -> None:  # type: ignore[no-untyped-def]
        resp = await async_client.get("/api/v1/deadlines")
        assert resp.status_code == 401

    async def test_list_deadlines_returns_structure(self, auth_headers) -> None:  # type: ignore[no-untyped-def]
        from unittest.mock import AsyncMock, MagicMock

        from httpx import ASGITransport, AsyncClient

        from tax_copilot.api.deps import get_db
        from tax_copilot.api.main import app

        mock_scalars = MagicMock()
        mock_scalars.all.return_value = []
        mock_execute_result = MagicMock()
        mock_execute_result.scalars.return_value = mock_scalars
        mock_db = AsyncMock()
        mock_db.execute.return_value = mock_execute_result

        async def override_get_db():
            yield mock_db

        app.dependency_overrides[get_db] = override_get_db
        try:
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                resp = await client.get("/api/v1/deadlines", headers=auth_headers)
        finally:
            app.dependency_overrides.pop(get_db, None)

        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert "total" in data

    async def test_generate_deadlines_for_year(self, auth_headers) -> None:  # type: ignore[no-untyped-def]
        """POST /api/v1/deadlines/generate → 한 해 기한 일괄 생성."""
        from unittest.mock import AsyncMock, MagicMock

        from httpx import ASGITransport, AsyncClient

        from tax_copilot.api.deps import get_db
        from tax_copilot.api.main import app

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(
            return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None))
        )
        mock_db.add = MagicMock()

        async def override_get_db():
            yield mock_db

        app.dependency_overrides[get_db] = override_get_db
        try:
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                resp = await client.post(
                    "/api/v1/deadlines/generate",
                    json={"client_company_id": 1, "fiscal_year": 2026},
                    headers=auth_headers,
                )
        finally:
            app.dependency_overrides.pop(get_db, None)

        assert resp.status_code == 201
        data = resp.json()
        assert "created_count" in data
        assert data["created_count"] == 6  # 4 VAT + 종합소득세 + 법인세

    async def test_client_cannot_generate_deadlines(self, async_client) -> None:  # type: ignore[no-untyped-def]
        from tax_copilot.auth.jwt import create_access_token

        token = create_access_token(user_id=10, tenant_id=1, role="client", client_company_id=42)
        resp = await async_client.post(
            "/api/v1/deadlines/generate",
            json={"client_company_id": 42, "fiscal_year": 2026},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 403
