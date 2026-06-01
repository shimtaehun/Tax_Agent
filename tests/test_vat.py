"""부가세 집계 API 테스트."""

import pytest


class TestVatAggregation:
    """core/tax/aggregation.py — 순수 집계 함수 단위 테스트."""

    def test_empty_list_returns_zeros(self) -> None:
        from tax_copilot.core.tax.aggregation import aggregate_vat

        result = aggregate_vat([])
        assert result["creditable"]["supply_value_krw"] == 0
        assert result["creditable"]["vat_krw"] == 0
        assert result["creditable"]["receipt_count"] == 0
        assert result["non_creditable"]["supply_value_krw"] == 0
        assert result["non_creditable"]["vat_krw"] == 0
        assert result["non_creditable"]["receipt_count"] == 0
        assert result["by_account_code"] == []

    def test_creditable_and_non_creditable_separated(self) -> None:
        from tax_copilot.core.tax.aggregation import aggregate_vat

        receipts = [
            {
                "account_code": "복리후생비",
                "parsed_data": {
                    "vat_creditable": True,
                    "calculation_result": {"supply_value_krw": 100_000, "vat_krw": 10_000},
                },
            },
            {
                "account_code": "접대비",
                "parsed_data": {
                    "vat_creditable": False,
                    "calculation_result": {"supply_value_krw": 50_000, "vat_krw": 5_000},
                },
            },
        ]
        result = aggregate_vat(receipts)
        assert result["creditable"]["supply_value_krw"] == 100_000
        assert result["creditable"]["vat_krw"] == 10_000
        assert result["creditable"]["receipt_count"] == 1
        assert result["non_creditable"]["supply_value_krw"] == 50_000
        assert result["non_creditable"]["vat_krw"] == 5_000
        assert result["non_creditable"]["receipt_count"] == 1

    def test_none_vat_creditable_excluded_from_sums(self) -> None:
        """vat_creditable=None 영수증은 공제/불공제 합계 모두 제외."""
        from tax_copilot.core.tax.aggregation import aggregate_vat

        receipts = [
            {
                "account_code": "미분류",
                "parsed_data": {
                    "vat_creditable": None,
                    "calculation_result": {"supply_value_krw": 30_000, "vat_krw": 3_000},
                },
            },
        ]
        result = aggregate_vat(receipts)
        assert result["creditable"]["supply_value_krw"] == 0
        assert result["non_creditable"]["supply_value_krw"] == 0

    def test_by_account_code_aggregates_all_receipts(self) -> None:
        """account_code별 집계는 vat_creditable 무관하게 모든 승인 영수증 포함."""
        from tax_copilot.core.tax.aggregation import aggregate_vat

        receipts = [
            {
                "account_code": "소모품비",
                "parsed_data": {
                    "vat_creditable": True,
                    "calculation_result": {"supply_value_krw": 20_000, "vat_krw": 2_000},
                },
            },
            {
                "account_code": "소모품비",
                "parsed_data": {
                    "vat_creditable": True,
                    "calculation_result": {"supply_value_krw": 30_000, "vat_krw": 3_000},
                },
            },
            {
                "account_code": "여비교통비",
                "parsed_data": {
                    "vat_creditable": False,
                    "calculation_result": {"supply_value_krw": 15_000, "vat_krw": 1_500},
                },
            },
        ]
        result = aggregate_vat(receipts)
        by_code = {item["account_code"]: item for item in result["by_account_code"]}
        assert by_code["소모품비"]["supply_value_krw"] == 50_000
        assert by_code["소모품비"]["receipt_count"] == 2
        assert by_code["여비교통비"]["supply_value_krw"] == 15_000
        assert by_code["여비교통비"]["receipt_count"] == 1

    def test_missing_calculation_result_treats_as_zero(self) -> None:
        """calculation_result 없는 영수증은 0으로 집계된다."""
        from tax_copilot.core.tax.aggregation import aggregate_vat

        receipts = [
            {
                "account_code": "복리후생비",
                "parsed_data": {
                    "vat_creditable": True,
                    "calculation_result": None,
                },
            },
        ]
        result = aggregate_vat(receipts)
        assert result["creditable"]["supply_value_krw"] == 0
        assert result["creditable"]["receipt_count"] == 1


@pytest.mark.anyio
class TestVatSummaryEndpoint:
    """GET /api/v1/vat/summary 엔드포인트 테스트."""

    async def test_requires_auth(self, async_client) -> None:  # type: ignore[no-untyped-def]
        resp = await async_client.get(
            "/api/v1/vat/summary",
            params={"client_company_id": 1, "from_date": "2026-01-01", "to_date": "2026-03-31"},
        )
        assert resp.status_code == 401

    async def test_returns_summary_structure(self, auth_headers) -> None:  # type: ignore[no-untyped-def]
        from unittest.mock import AsyncMock, MagicMock

        from httpx import ASGITransport, AsyncClient

        from tax_copilot.api.deps import get_db
        from tax_copilot.api.main import app

        mock_scalars = MagicMock()
        mock_scalars.all.return_value = []
        mock_execute_result = MagicMock()
        mock_execute_result.scalars.return_value = mock_scalars
        mock_db = AsyncMock()
        invoice_scalars = MagicMock()
        invoice_scalars.all.return_value = []
        invoice_result = MagicMock()
        invoice_result.scalars.return_value = invoice_scalars
        mock_db.execute = AsyncMock(side_effect=[mock_execute_result, invoice_result])

        async def override_get_db():
            yield mock_db

        app.dependency_overrides[get_db] = override_get_db
        try:
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                resp = await client.get(
                    "/api/v1/vat/summary",
                    params={
                        "client_company_id": 1,
                        "from_date": "2026-01-01",
                        "to_date": "2026-03-31",
                    },
                    headers=auth_headers,
                )
        finally:
            app.dependency_overrides.pop(get_db, None)

        assert resp.status_code == 200
        data = resp.json()
        assert "creditable" in data
        assert "non_creditable" in data
        assert "by_account_code" in data
        assert "pending_review_count" in data

    async def test_missing_required_params(self, async_client, auth_headers) -> None:  # type: ignore[no-untyped-def]
        resp = await async_client.get(
            "/api/v1/vat/summary",
            params={"client_company_id": 1},
            headers=auth_headers,
        )
        assert resp.status_code == 422

    async def test_client_cannot_query_other_company(self, async_client) -> None:  # type: ignore[no-untyped-def]
        from tax_copilot.auth.jwt import create_access_token

        token = create_access_token(user_id=10, tenant_id=1, role="client", client_company_id=42)
        resp = await async_client.get(
            "/api/v1/vat/summary",
            params={"client_company_id": 99, "from_date": "2026-01-01", "to_date": "2026-03-31"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 403
