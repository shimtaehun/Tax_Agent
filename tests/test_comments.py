"""영수증 코멘트 API 테스트."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from tax_copilot.api.deps import get_db
from tax_copilot.api.main import app
from tax_copilot.auth.jwt import create_access_token
from tax_copilot.infra.db.models.receipt import Receipt
from tax_copilot.infra.db.models.receipt_comment import ReceiptComment


def _client_headers(company_id: int) -> dict[str, str]:
    token = create_access_token(
        user_id=10, tenant_id=1, role="client", client_company_id=company_id
    )
    return {"Authorization": f"Bearer {token}"}


def _staff_headers() -> dict[str, str]:
    token = create_access_token(user_id=1, tenant_id=1, role="staff")
    return {"Authorization": f"Bearer {token}"}


def _make_receipt(receipt_id: int, company_id: int) -> MagicMock:
    r = MagicMock(spec=Receipt)
    r.id = receipt_id
    r.tenant_id = 1
    r.client_company_id = company_id
    return r


def _make_comment(comment_id: int, receipt_id: int) -> MagicMock:
    c = MagicMock(spec=ReceiptComment)
    c.id = comment_id
    c.receipt_id = receipt_id
    c.author_id = 1
    c.body = "테스트 코멘트"
    c.created_at = datetime.now(UTC)
    return c


@pytest.mark.anyio
class TestListComments:
    async def test_staff_can_list_comments(self) -> None:
        receipt = _make_receipt(5, company_id=42)
        comments = [_make_comment(1, 5), _make_comment(2, 5)]

        scalars_mock = MagicMock()
        scalars_mock.all.return_value = comments

        receipt_result = MagicMock()
        receipt_result.scalar_one_or_none.return_value = receipt
        comments_result = MagicMock()
        comments_result.scalars.return_value = scalars_mock

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(side_effect=[receipt_result, comments_result])

        async def override_get_db():
            yield mock_db

        app.dependency_overrides[get_db] = override_get_db
        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
                resp = await c.get("/api/v1/receipts/5/comments", headers=_staff_headers())
        finally:
            app.dependency_overrides.pop(get_db, None)

        assert resp.status_code == 200
        assert len(resp.json()["items"]) == 2

    async def test_client_cannot_access_other_company_comments(self) -> None:
        """client_company_id=42 사용자가 company_id=99 영수증 코멘트 조회 시 400."""
        receipt = _make_receipt(5, company_id=99)  # 다른 회사 영수증

        receipt_result = MagicMock()
        receipt_result.scalar_one_or_none.return_value = receipt

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=receipt_result)

        async def override_get_db():
            yield mock_db

        app.dependency_overrides[get_db] = override_get_db
        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
                resp = await c.get("/api/v1/receipts/5/comments", headers=_client_headers(42))
        finally:
            app.dependency_overrides.pop(get_db, None)

        assert resp.status_code == 400


@pytest.mark.anyio
class TestCreateComment:
    async def test_staff_can_post_comment(self) -> None:
        receipt = _make_receipt(5, company_id=42)
        new_comment = _make_comment(10, 5)
        new_comment.author_id = 1

        receipt_result = MagicMock()
        receipt_result.scalar_one_or_none.return_value = receipt

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=receipt_result)
        mock_db.flush = AsyncMock()
        mock_db.commit = AsyncMock()
        mock_db.refresh = AsyncMock()

        def _fake_add(obj: object) -> None:
            if isinstance(obj, ReceiptComment):
                obj.id = 10  # type: ignore[assignment]
                obj.created_at = datetime.now(UTC)  # type: ignore[assignment]

        mock_db.add = MagicMock(side_effect=_fake_add)

        async def override_get_db():
            yield mock_db

        app.dependency_overrides[get_db] = override_get_db
        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
                resp = await c.post(
                    "/api/v1/receipts/5/comments",
                    headers=_staff_headers(),
                    json={"body": "검토 완료했습니다."},
                )
        finally:
            app.dependency_overrides.pop(get_db, None)

        assert resp.status_code == 201
        assert resp.json()["body"] == "검토 완료했습니다."

    async def test_client_can_post_comment_on_own_receipt(self) -> None:
        receipt = _make_receipt(5, company_id=42)
        new_comment = _make_comment(11, 5)
        new_comment.author_id = 10

        receipt_result = MagicMock()
        receipt_result.scalar_one_or_none.return_value = receipt

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=receipt_result)
        mock_db.flush = AsyncMock()
        mock_db.commit = AsyncMock()
        mock_db.refresh = AsyncMock()

        def _fake_add(obj: object) -> None:
            if isinstance(obj, ReceiptComment):
                obj.id = 11  # type: ignore[assignment]
                obj.created_at = datetime.now(UTC)  # type: ignore[assignment]

        mock_db.add = MagicMock(side_effect=_fake_add)

        async def override_get_db():
            yield mock_db

        app.dependency_overrides[get_db] = override_get_db
        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
                resp = await c.post(
                    "/api/v1/receipts/5/comments",
                    headers=_client_headers(42),
                    json={"body": "영수증 첨부했습니다."},
                )
        finally:
            app.dependency_overrides.pop(get_db, None)

        assert resp.status_code == 201
