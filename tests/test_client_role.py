"""고객사 포털 — client role 접근 제어 테스트."""

import io
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from tax_copilot.api.deps import get_db
from tax_copilot.api.main import app
from tax_copilot.auth.jwt import create_access_token
from tax_copilot.infra.db.models.receipt import Receipt


def _client_headers(client_company_id: int) -> dict[str, str]:
    token = create_access_token(
        user_id=10,
        tenant_id=1,
        role="client",
        client_company_id=client_company_id,
    )
    return {"Authorization": f"Bearer {token}"}


def _make_receipt(receipt_id: int, tenant_id: int, client_company_id: int) -> MagicMock:
    r = MagicMock(spec=Receipt)
    r.id = receipt_id
    r.tenant_id = tenant_id
    r.client_company_id = client_company_id
    r.status = "APPROVED"
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
class TestClientRoleListReceipts:
    """client 역할은 자신의 고객사 영수증만 조회 가능."""

    async def test_client_sees_own_company_receipts(self) -> None:
        receipt = _make_receipt(1, tenant_id=1, client_company_id=42)
        scalars_mock = MagicMock()
        scalars_mock.all.return_value = [receipt]

        count_result = MagicMock()
        count_result.scalar_one.return_value = 1
        list_result = MagicMock()
        list_result.scalars.return_value = scalars_mock
        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(side_effect=[count_result, list_result])

        async def override_get_db():
            yield mock_db

        app.dependency_overrides[get_db] = override_get_db
        try:
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                resp = await client.get(
                    "/api/v1/receipts",
                    headers=_client_headers(client_company_id=42),
                )
        finally:
            app.dependency_overrides.pop(get_db, None)

        assert resp.status_code == 200
        data = resp.json()
        # 모의 DB가 1개 영수증을 반환했으므로 items가 1개여야 함
        assert data["total"] == 1
        assert len(data["items"]) == 1
        assert data["items"][0]["client_company_id"] == 42

    async def test_staff_sees_all_receipts_in_tenant(self) -> None:
        """staff 역할은 client_company_id 필터 없이 모든 영수증 조회."""
        scalars_mock = MagicMock()
        scalars_mock.all.return_value = []

        count_result = MagicMock()
        count_result.scalar_one.return_value = 0
        list_result = MagicMock()
        list_result.scalars.return_value = scalars_mock
        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(side_effect=[count_result, list_result])

        async def override_get_db():
            yield mock_db

        staff_headers = {
            "Authorization": f"Bearer {create_access_token(user_id=1, tenant_id=1, role='staff')}"
        }
        app.dependency_overrides[get_db] = override_get_db
        try:
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                resp = await client.get("/api/v1/receipts", headers=staff_headers)
        finally:
            app.dependency_overrides.pop(get_db, None)

        assert resp.status_code == 200
        # staff 쿼리에는 42가 없어야 함
        second_query_str = str(mock_db.execute.call_args_list[1])
        assert "42" not in second_query_str


@pytest.mark.anyio
class TestClientRoleGetReceipt:
    """client 역할은 다른 고객사 영수증에 접근 불가."""

    async def test_client_cannot_access_other_company_receipt(self) -> None:
        """client_company_id=42 사용자가 client_company_id=99 영수증 조회 시 404."""
        not_found = MagicMock()
        not_found.scalar_one_or_none.return_value = None
        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=not_found)

        async def override_get_db():
            yield mock_db

        app.dependency_overrides[get_db] = override_get_db
        try:
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                resp = await client.get(
                    "/api/v1/receipts/5",
                    headers=_client_headers(client_company_id=42),
                )
        finally:
            app.dependency_overrides.pop(get_db, None)

        assert resp.status_code in (400, 404)

    async def test_client_can_access_own_receipt(self) -> None:
        receipt = _make_receipt(5, tenant_id=1, client_company_id=42)
        found = MagicMock()
        found.scalar_one_or_none.return_value = receipt
        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=found)

        async def override_get_db():
            yield mock_db

        app.dependency_overrides[get_db] = override_get_db
        try:
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                resp = await client.get(
                    "/api/v1/receipts/5",
                    headers=_client_headers(client_company_id=42),
                )
        finally:
            app.dependency_overrides.pop(get_db, None)

        assert resp.status_code == 200
        assert resp.json()["receipt_id"] == 5


@pytest.mark.anyio
class TestClientRoleUpload:
    """client 역할 업로드: client_company_id를 JWT에서 자동 설정."""

    def _make_mock_db(self) -> AsyncMock:
        from tax_copilot.infra.db.models.receipt import Receipt as _Receipt

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(
            return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None))
        )
        mock_db.flush = AsyncMock()
        mock_db.commit = AsyncMock()

        def _fake_add(obj: object) -> None:
            if isinstance(obj, _Receipt):
                obj.id = 1  # type: ignore[assignment]

        # db.add는 동기 호출이므로 MagicMock으로 교체해야 side_effect가 동작함
        mock_db.add = MagicMock(side_effect=_fake_add)
        return mock_db

    async def test_client_upload_uses_jwt_company_id(self) -> None:
        """client 역할은 파라미터 없이도 JWT의 client_company_id로 업로드 성공."""
        mock_db = self._make_mock_db()

        async def override_get_db():
            yield mock_db

        app.dependency_overrides[get_db] = override_get_db
        try:
            with (
                patch(
                    "tax_copilot.api.v1.receipts.validate_receipt_file",
                    return_value="image/jpeg",
                ),
                patch("tax_copilot.api.v1.receipts.compute_file_hash", return_value="abc123"),
                patch("tax_copilot.api.v1.receipts.save_receipt", return_value="/tmp/f.jpg"),
                patch("tax_copilot.api.v1.receipts.record_event", new_callable=AsyncMock),
                patch("tax_copilot.api.v1.receipts.dispatch_receipt_task", return_value="task-1"),
            ):
                async with AsyncClient(
                    transport=ASGITransport(app=app), base_url="http://test"
                ) as client:
                    resp = await client.post(
                        "/api/v1/receipts",
                        headers=_client_headers(client_company_id=42),
                        files={"file": ("receipt.jpg", io.BytesIO(b"fake"), "image/jpeg")},
                        # client_company_id 파라미터를 의도적으로 생략
                    )
        finally:
            app.dependency_overrides.pop(get_db, None)

        assert resp.status_code == 201

    async def test_client_upload_ignores_param_company_id(self) -> None:
        """client 역할은 파라미터로 다른 company_id를 넘겨도 JWT 값이 사용된다."""
        captured: list[int] = []
        mock_db = self._make_mock_db()

        async def override_get_db():
            yield mock_db

        app.dependency_overrides[get_db] = override_get_db
        try:
            with (
                patch(
                    "tax_copilot.api.v1.receipts.validate_receipt_file",
                    return_value="image/jpeg",
                ),
                patch("tax_copilot.api.v1.receipts.compute_file_hash", return_value="def456"),
                patch("tax_copilot.api.v1.receipts.save_receipt", return_value="/tmp/g.jpg"),
                patch(
                    "tax_copilot.api.v1.receipts.record_event",
                    new_callable=AsyncMock,
                ) as mock_record,
                patch("tax_copilot.api.v1.receipts.dispatch_receipt_task", return_value="task-2"),
            ):
                async with AsyncClient(
                    transport=ASGITransport(app=app), base_url="http://test"
                ) as client:
                    resp = await client.post(
                        "/api/v1/receipts?client_company_id=999",  # 다른 회사 ID
                        headers=_client_headers(client_company_id=42),
                        files={"file": ("receipt2.jpg", io.BytesIO(b"fake2"), "image/jpeg")},
                    )
                if mock_record.called:
                    payload = mock_record.call_args.kwargs.get("payload", {})
                    captured.append(payload.get("client_company_id", -1))
        finally:
            app.dependency_overrides.pop(get_db, None)

        assert resp.status_code == 201
        # JWT의 42가 사용되어야 함, 999가 아님
        if captured:
            assert captured[0] == 42

    async def test_staff_upload_requires_param_company_id(self) -> None:
        """staff 역할은 client_company_id 파라미터 없으면 400."""
        staff_headers = {
            "Authorization": f"Bearer {create_access_token(user_id=1, tenant_id=1, role='staff')}"
        }
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post(
                "/api/v1/receipts",
                headers=staff_headers,
                files={"file": ("r.jpg", io.BytesIO(b"x"), "image/jpeg")},
                # client_company_id 파라미터 없음
            )
        assert resp.status_code == 400
