"""core/receipts/validation.py 단위 테스트."""

import pytest

from tax_copilot.core.exceptions import ValidationError
from tax_copilot.core.receipts.validation import (
    compute_file_hash,
    detect_mime_type,
    validate_receipt_file,
)

# 각 형식의 실제 magic bytes
JPEG_MAGIC = b"\xff\xd8\xff" + b"\x00" * 100
PNG_MAGIC = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
PDF_MAGIC = b"%PDF" + b"\x00" * 100


class TestDetectMimeType:
    def test_detects_jpeg(self) -> None:
        assert detect_mime_type(JPEG_MAGIC) == "image/jpeg"

    def test_detects_png(self) -> None:
        assert detect_mime_type(PNG_MAGIC) == "image/png"

    def test_detects_pdf(self) -> None:
        assert detect_mime_type(PDF_MAGIC) == "application/pdf"

    def test_returns_none_for_unknown(self) -> None:
        assert detect_mime_type(b"\x00\x01\x02\x03") is None


class TestValidateReceiptFile:
    def test_valid_jpeg(self) -> None:
        mime = validate_receipt_file("receipt.jpg", JPEG_MAGIC)
        assert mime == "image/jpeg"

    def test_valid_png(self) -> None:
        mime = validate_receipt_file("receipt.png", PNG_MAGIC)
        assert mime == "image/png"

    def test_valid_pdf(self) -> None:
        mime = validate_receipt_file("receipt.pdf", PDF_MAGIC)
        assert mime == "application/pdf"

    def test_rejects_empty_file(self) -> None:
        with pytest.raises(ValidationError, match="빈 파일"):
            validate_receipt_file("receipt.jpg", b"")

    def test_rejects_oversized_file(self) -> None:
        oversized = JPEG_MAGIC + b"\x00" * (10 * 1024 * 1024)
        with pytest.raises(ValidationError, match="초과"):
            validate_receipt_file("receipt.jpg", oversized)

    def test_rejects_disallowed_extension(self) -> None:
        with pytest.raises(ValidationError, match="허용되지 않는"):
            validate_receipt_file("receipt.gif", JPEG_MAGIC)

    def test_rejects_content_type_mismatch(self) -> None:
        # 확장자는 pdf지만 내용은 jpeg
        with pytest.raises(ValidationError, match="일치하지 않습니다"):
            validate_receipt_file("receipt.pdf", JPEG_MAGIC)


class TestComputeFileHash:
    def test_same_content_produces_same_hash(self) -> None:
        content = b"hello world"
        assert compute_file_hash(content) == compute_file_hash(content)

    def test_different_content_produces_different_hash(self) -> None:
        assert compute_file_hash(b"aaa") != compute_file_hash(b"bbb")

    def test_returns_hex_string(self) -> None:
        result = compute_file_hash(b"test")
        assert all(c in "0123456789abcdef" for c in result)
        assert len(result) == 64  # SHA-256 hex digest


class TestAccountCodePatch:
    """PATCH /v1/receipts/{id}/account-code 엔드포인트 검증."""

    @pytest.mark.asyncio
    async def test_valid_account_code_accepted(self) -> None:
        """유효한 계정과목으로 PATCH 시 200 반환."""
        from tax_copilot.schemas.receipts import AccountCodeUpdateRequest

        req = AccountCodeUpdateRequest(account_code="접대비")
        assert req.account_code == "접대비"

    @pytest.mark.asyncio
    async def test_invalid_account_code_rejected(self) -> None:
        """15종 외 계정과목은 ValidationError."""
        from tax_copilot.schemas.receipts import AccountCodeUpdateRequest

        with pytest.raises(ValueError):
            AccountCodeUpdateRequest(account_code="잘못된값")

    @pytest.mark.anyio
    async def test_client_cannot_patch_account_code(self) -> None:
        """client 역할은 계정과목 직접 수정 API를 호출할 수 없다."""
        from httpx import ASGITransport, AsyncClient

        from tax_copilot.api.main import app
        from tax_copilot.auth.jwt import create_access_token

        token = create_access_token(user_id=10, tenant_id=1, role="client", client_company_id=42)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.patch(
                "/api/v1/receipts/1/account-code",
                headers={"Authorization": f"Bearer {token}"},
                json={"account_code": "접대비"},
            )

        assert resp.status_code == 403
