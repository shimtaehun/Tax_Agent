from tax_copilot.core.exceptions import ValidationError

MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024  # 10MB

_ALLOWED_MAGIC: dict[bytes, str] = {
    b"\xff\xd8\xff": "image/jpeg",
    b"\x89PNG\r\n\x1a\n": "image/png",
    b"%PDF": "application/pdf",
    b"II*\x00": "image/tiff",  # TIFF little-endian
    b"MM\x00*": "image/tiff",  # TIFF big-endian
}


def validate_upload(filename: str, content: bytes) -> str:
    """Returns detected mime_type. Raises ValidationError on failure."""
    if len(content) > MAX_FILE_SIZE_BYTES:
        raise ValidationError(f"File too large: {len(content)} bytes (max {MAX_FILE_SIZE_BYTES})")
    if not content:
        raise ValidationError("Empty file")

    for magic, mime in _ALLOWED_MAGIC.items():
        if content.startswith(magic):
            return mime

    raise ValidationError(f"Unsupported file type for '{filename}'. Allowed: JPEG, PNG, PDF, TIFF")
