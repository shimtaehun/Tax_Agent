import hashlib
from pathlib import Path

from tax_copilot.core.config import settings


def compute_sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def save_file(tenant_id: int, file_hash: str, content: bytes, suffix: str) -> str:
    """Saves file and returns relative path string."""
    base = Path(settings.local_storage_path) / str(tenant_id)
    base.mkdir(parents=True, exist_ok=True)
    dest = base / f"{file_hash}{suffix}"
    if not dest.exists():
        dest.write_bytes(content)
    return str(dest)


def _ext_from_mime(mime: str) -> str:
    return {
        "image/jpeg": ".jpg",
        "image/png": ".png",
        "image/tiff": ".tiff",
        "application/pdf": ".pdf",
    }.get(mime, ".bin")


def store_receipt(tenant_id: int, content: bytes, mime: str) -> tuple[str, str]:
    """Returns (file_path, file_hash)."""
    file_hash = compute_sha256(content)
    path = save_file(tenant_id, file_hash, content, _ext_from_mime(mime))
    return path, file_hash
