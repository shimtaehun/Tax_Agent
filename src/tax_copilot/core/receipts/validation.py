import hashlib

from tax_copilot.core.exceptions import ValidationError

ALLOWED_MIME_TYPES = {"image/jpeg", "image/png", "application/pdf"}
MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024  # 10MB

# 허용 확장자 → 기대 MIME 매핑
_EXT_TO_MIME: dict[str, str] = {
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "png": "image/png",
    "pdf": "application/pdf",
}

# magic bytes로 실제 파일 형식 확인 (Content-Type 헤더는 믿지 않음)
_MAGIC: dict[bytes, str] = {
    b"\xff\xd8\xff": "image/jpeg",
    b"\x89PNG\r\n\x1a\n": "image/png",
    b"%PDF": "application/pdf",
}


def detect_mime_type(data: bytes) -> str | None:
    """파일 첫 바이트로 실제 MIME 타입을 판별한다."""
    for magic, mime in _MAGIC.items():
        if data[: len(magic)] == magic:
            return mime
    return None


def validate_receipt_file(filename: str, content: bytes) -> str:
    """파일 크기, 확장자, magic bytes를 검증하고 실제 MIME 타입을 반환한다.

    Returns:
        Detected MIME type string.

    Raises:
        ValidationError: 검증 실패 시.
    """
    if len(content) == 0:
        raise ValidationError("빈 파일은 업로드할 수 없습니다.")
    if len(content) > MAX_FILE_SIZE_BYTES:
        raise ValidationError(f"파일 크기가 {MAX_FILE_SIZE_BYTES // 1024 // 1024}MB를 초과합니다.")

    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    expected_mime = _EXT_TO_MIME.get(ext)
    if expected_mime is None:
        raise ValidationError(f"허용되지 않는 파일 형식입니다: .{ext}")

    mime = detect_mime_type(content)
    if mime is None or mime not in ALLOWED_MIME_TYPES:
        raise ValidationError("파일 내용이 허용된 형식과 일치하지 않습니다.")

    # 확장자와 실제 내용 형식이 다른 경우 거부 (content-type spoofing 방지)
    if mime != expected_mime:
        raise ValidationError("파일 확장자와 내용 형식이 일치하지 않습니다.")

    return mime


def compute_file_hash(content: bytes) -> str:
    """SHA-256으로 파일 내용 해시를 계산한다. 중복 업로드 방지에 사용."""
    return hashlib.sha256(content).hexdigest()
