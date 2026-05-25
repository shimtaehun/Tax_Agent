from pathlib import Path

from tax_copilot.core.config import settings
from tax_copilot.core.exceptions import StorageError


def _receipt_path(tenant_id: int, file_hash: str, ext: str) -> Path:
    """receipts/{tenant_id}/{hash[:2]}/{hash}.{ext} 경로를 반환한다."""
    base = Path(settings.local_storage_path) / "receipts" / str(tenant_id) / file_hash[:2]
    return base / f"{file_hash}.{ext}"


def save_receipt(tenant_id: int, file_hash: str, ext: str, content: bytes) -> str:
    """파일을 로컬에 저장하고 상대 경로를 반환한다.

    Raises:
        StorageError: 디스크 쓰기 실패 시.
    """
    path = _receipt_path(tenant_id, file_hash, ext)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
    except OSError as exc:
        raise StorageError(f"파일 저장 실패: {exc}") from exc
    return str(path)


def load_receipt(file_path: str) -> bytes:
    """저장된 파일을 읽어 bytes로 반환한다.

    Raises:
        StorageError: 파일이 없거나, 스토리지 루트 외부 경로이거나, 읽기 실패 시.
    """
    storage_root = Path(settings.local_storage_path).resolve()
    path = Path(file_path).resolve()
    if not str(path).startswith(str(storage_root)):
        raise StorageError(f"허용되지 않은 파일 경로입니다: {file_path}")
    if not path.exists():
        raise StorageError(f"파일을 찾을 수 없습니다: {file_path}")
    try:
        return path.read_bytes()
    except OSError as exc:
        raise StorageError(f"파일 읽기 실패: {exc}") from exc
