"""영수증 일괄 업로드 테스트."""

import io

import pytest


@pytest.mark.anyio
class TestBatchUpload:
    """POST /api/v1/receipts/batch 엔드포인트."""

    async def test_requires_auth(self, async_client) -> None:  # type: ignore[no-untyped-def]
        resp = await async_client.post("/api/v1/receipts/batch")
        assert resp.status_code == 401

    async def test_batch_upload_returns_batch_id(self, auth_headers) -> None:  # type: ignore[no-untyped-def]
        """정상 파일 2개 → batch_id + results 반환."""
        from unittest.mock import AsyncMock, MagicMock, patch

        from httpx import ASGITransport, AsyncClient

        from tax_copilot.api.deps import get_db
        from tax_copilot.api.main import app
        from tax_copilot.infra.db.models.receipt import Receipt

        mock_receipt = MagicMock(spec=Receipt)
        mock_receipt.id = 1
        mock_receipt.status = "PENDING"

        mock_db = AsyncMock()
        mock_db.flush = AsyncMock()
        mock_db.commit = AsyncMock()
        mock_db.execute = AsyncMock(
            return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None))
        )

        async def override_get_db():
            yield mock_db

        # 파일 저장, 해시, 유효성, task dispatch를 모두 mock
        with (
            patch("tax_copilot.api.v1.receipts.validate_receipt_file", return_value="image/jpeg"),
            patch("tax_copilot.api.v1.receipts.compute_file_hash", side_effect=["hash1", "hash2"]),
            patch("tax_copilot.api.v1.receipts.save_receipt", return_value="/tmp/f.jpg"),  # noqa: S108
            patch("tax_copilot.api.v1.receipts.dispatch_receipt_task", return_value="task-id"),
            patch("tax_copilot.api.v1.receipts.record_event", new=AsyncMock()),
        ):
            app.dependency_overrides[get_db] = override_get_db
            try:
                async with AsyncClient(
                    transport=ASGITransport(app=app), base_url="http://test"
                ) as client:
                    # Receipt DB 삽입 모의: add() 후 flush()가 id를 세팅한다고 가정
                    added_receipts: list[Receipt] = []

                    def fake_add(obj: object) -> None:
                        if isinstance(obj, Receipt):
                            obj.id = len(added_receipts) + 1  # type: ignore[assignment]
                            added_receipts.append(obj)

                    mock_db.add.side_effect = fake_add

                    resp = await client.post(
                        "/api/v1/receipts/batch",
                        params={"client_company_id": 1},
                        files=[
                            ("files", ("a.jpg", io.BytesIO(b"fake-jpg-1"), "image/jpeg")),
                            ("files", ("b.jpg", io.BytesIO(b"fake-jpg-2"), "image/jpeg")),
                        ],
                        headers=auth_headers,
                    )
            finally:
                app.dependency_overrides.pop(get_db, None)

        assert resp.status_code == 201
        data = resp.json()
        assert "batch_id" in data
        assert "results" in data
        assert "total" in data

    async def test_duplicate_file_skipped(self, auth_headers) -> None:  # type: ignore[no-untyped-def]
        """이미 업로드된 파일은 skipped 처리된다."""
        from unittest.mock import AsyncMock, MagicMock, patch

        from httpx import ASGITransport, AsyncClient

        from tax_copilot.api.deps import get_db
        from tax_copilot.api.main import app
        from tax_copilot.infra.db.models.receipt import Receipt

        existing = MagicMock(spec=Receipt)
        existing.id = 99

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(
            return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=existing))
        )

        async def override_get_db():
            yield mock_db

        with (
            patch("tax_copilot.api.v1.receipts.validate_receipt_file", return_value="image/jpeg"),
            patch("tax_copilot.api.v1.receipts.compute_file_hash", return_value="dup-hash"),
        ):
            app.dependency_overrides[get_db] = override_get_db
            try:
                async with AsyncClient(
                    transport=ASGITransport(app=app), base_url="http://test"
                ) as client:
                    resp = await client.post(
                        "/api/v1/receipts/batch",
                        params={"client_company_id": 1},
                        files=[
                            ("files", ("dup.jpg", io.BytesIO(b"dup"), "image/jpeg")),
                        ],
                        headers=auth_headers,
                    )
            finally:
                app.dependency_overrides.pop(get_db, None)

        assert resp.status_code == 201
        data = resp.json()
        assert data["skipped_count"] == 1

    async def test_too_many_files_rejected(self, async_client, auth_headers) -> None:  # type: ignore[no-untyped-def]
        """21개 파일 → 422."""
        from unittest.mock import patch

        with patch("tax_copilot.api.v1.receipts.validate_receipt_file", return_value="image/jpeg"):
            resp = await async_client.post(
                "/api/v1/receipts/batch",
                params={"client_company_id": 1},
                files=[("files", (f"{i}.jpg", io.BytesIO(b"x"), "image/jpeg")) for i in range(21)],
                headers=auth_headers,
            )
        assert resp.status_code in (400, 422)
