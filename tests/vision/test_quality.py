from struct import pack

from tax_copilot.core.vision import StaticReceiptExtractor, check_image_quality


def _png_header(width: int, height: int, padding: int = 256) -> bytes:
    return (
        b"\x89PNG\r\n\x1a\n"
        + b"\x00\x00\x00\rIHDR"
        + pack(">II", width, height)
        + b"\x00" * padding
    )


def test_png_quality_passes_for_large_image() -> None:
    result = check_image_quality(_png_header(1200, 800), "image/png")

    assert result.is_readable
    assert result.dimensions is not None
    assert result.dimensions.width == 1200


def test_png_quality_fails_for_small_image() -> None:
    result = check_image_quality(_png_header(320, 180), "image/png")

    assert not result.is_readable
    assert result.status == "unreadable"
    assert result.reason == "image_too_small"


def test_static_receipt_extractor_returns_valid_parsed_receipt() -> None:
    parsed = StaticReceiptExtractor().extract(
        file_path="local://receipt.png",
        mime_type="image/png",
    )

    assert parsed.merchant_name == "Mock Merchant"
    assert parsed.total_amount_krw == 11000
