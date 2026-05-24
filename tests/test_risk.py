"""세무조사 리스크 스코어링 테스트."""

import pytest


class TestRiskScoring:
    """core/tax/risk_scoring.py — 순수 리스크 계산 함수 단위 테스트."""

    def test_empty_stats_returns_zero_score(self) -> None:
        from tax_copilot.core.tax.risk_scoring import score_risk

        result = score_risk(
            {
                "total_approved": 0,
                "total_supply_value_krw": 0,
                "entertainment_supply_value_krw": 0,
                "simplified_receipt_count": 0,
                "risk_flag_count": 0,
                "duplicate_suspect_count": 0,
            }
        )
        assert result["score"] == 0
        assert result["flags"] == []

    def test_high_entertainment_ratio_raises_score(self) -> None:
        """접대비 비율 35% → entertainment 컴포넌트 최고점."""
        from tax_copilot.core.tax.risk_scoring import score_risk

        result = score_risk(
            {
                "total_approved": 10,
                "total_supply_value_krw": 1_000_000,
                "entertainment_supply_value_krw": 350_000,  # 35%
                "simplified_receipt_count": 0,
                "risk_flag_count": 0,
                "duplicate_suspect_count": 0,
            }
        )
        assert result["score"] >= 40
        assert any("접대비" in f for f in result["flags"])

    def test_high_simplified_ratio_raises_score(self) -> None:
        """간이영수증 비율 50% → simplified 컴포넌트 최고점."""
        from tax_copilot.core.tax.risk_scoring import score_risk

        result = score_risk(
            {
                "total_approved": 10,
                "total_supply_value_krw": 500_000,
                "entertainment_supply_value_krw": 0,
                "simplified_receipt_count": 5,  # 50%
                "risk_flag_count": 0,
                "duplicate_suspect_count": 0,
            }
        )
        assert result["score"] >= 30
        assert any("간이영수증" in f for f in result["flags"])

    def test_no_risk_returns_low_score(self) -> None:
        """정상적인 지출 패턴 → 낮은 점수."""
        from tax_copilot.core.tax.risk_scoring import score_risk

        result = score_risk(
            {
                "total_approved": 20,
                "total_supply_value_krw": 2_000_000,
                "entertainment_supply_value_krw": 50_000,  # 2.5%
                "simplified_receipt_count": 2,  # 10%
                "risk_flag_count": 1,  # 5%
                "duplicate_suspect_count": 0,
            }
        )
        assert result["score"] < 20

    def test_score_capped_at_100(self) -> None:
        """최악 조합도 100을 넘지 않는다."""
        from tax_copilot.core.tax.risk_scoring import score_risk

        result = score_risk(
            {
                "total_approved": 10,
                "total_supply_value_krw": 1_000_000,
                "entertainment_supply_value_krw": 1_000_000,  # 100%
                "simplified_receipt_count": 10,  # 100%
                "risk_flag_count": 10,  # 100%
                "duplicate_suspect_count": 10,  # 100%
            }
        )
        assert result["score"] <= 100

    def test_explanation_generated(self) -> None:
        """설명 문자열이 반환된다."""
        from tax_copilot.core.tax.risk_scoring import score_risk

        result = score_risk(
            {
                "total_approved": 10,
                "total_supply_value_krw": 1_000_000,
                "entertainment_supply_value_krw": 400_000,
                "simplified_receipt_count": 0,
                "risk_flag_count": 0,
                "duplicate_suspect_count": 0,
            }
        )
        assert isinstance(result["explanation"], str)
        assert len(result["explanation"]) > 0


@pytest.mark.anyio
class TestRiskScoreEndpoint:
    """GET /api/v1/risk/score 엔드포인트 테스트."""

    async def test_requires_auth(self, async_client) -> None:  # type: ignore[no-untyped-def]
        resp = await async_client.get(
            "/api/v1/risk/score",
            params={"client_company_id": 1, "from_date": "2026-01-01", "to_date": "2026-03-31"},
        )
        assert resp.status_code == 401

    async def test_returns_risk_structure(self, auth_headers) -> None:  # type: ignore[no-untyped-def]
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
                resp = await client.get(
                    "/api/v1/risk/score",
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
        assert "score" in data
        assert "flags" in data
        assert "explanation" in data
        assert "indicators" in data
