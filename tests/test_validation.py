import pytest

from tax_copilot.core.exceptions import ValidationError
from tax_copilot.core.receipts.validation import validate_upload

JPEG_MAGIC = b"\xff\xd8\xff" + b"\x00" * 100
PNG_MAGIC = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100


def test_valid_jpeg() -> None:
    mime = validate_upload("receipt.jpg", JPEG_MAGIC)
    assert mime == "image/jpeg"


def test_valid_png() -> None:
    mime = validate_upload("receipt.png", PNG_MAGIC)
    assert mime == "image/png"


def test_invalid_file_type() -> None:
    with pytest.raises(ValidationError, match="Unsupported"):
        validate_upload("file.txt", b"plaintext content here")


def test_empty_file() -> None:
    with pytest.raises(ValidationError, match="Empty"):
        validate_upload("empty.jpg", b"")


def test_file_too_large() -> None:
    big = b"\xff\xd8\xff" + b"\x00" * (10 * 1024 * 1024 + 1)
    with pytest.raises(ValidationError, match="too large"):
        validate_upload("big.jpg", big)
