from collections.abc import Callable
from dataclasses import dataclass

from tax_copilot.core.exceptions import DuplicateReceiptError


@dataclass(frozen=True)
class ReceiptTaskPayload:
    tenant_id: int
    receipt_id: int
    file_path: str
    file_hash: str
    attempt_number: int


class InMemoryReceiptLock:
    def __init__(self) -> None:
        self._locked_keys: set[str] = set()

    def acquire(self, key: str, ttl_seconds: int) -> bool:
        if key in self._locked_keys:
            return False
        self._locked_keys.add(key)
        return True

    def release(self, key: str) -> None:
        self._locked_keys.discard(key)


def build_receipt_task_id(payload: ReceiptTaskPayload) -> str:
    return f"receipt-{payload.tenant_id}-{payload.file_hash[:16]}-a{payload.attempt_number}"


def build_receipt_lock_key(payload: ReceiptTaskPayload) -> str:
    return f"lock:receipt:{payload.tenant_id}:{payload.file_hash}"


def dispatch_receipt_task(
    payload: ReceiptTaskPayload,
    *,
    acquire_lock: Callable[[str, int], bool],
    send_task: Callable[[ReceiptTaskPayload, str], str],
    lock_ttl_seconds: int = 300,
) -> str:
    lock_key = build_receipt_lock_key(payload)
    if not acquire_lock(lock_key, lock_ttl_seconds):
        raise DuplicateReceiptError("Receipt is already being processed")

    task_id = build_receipt_task_id(payload)
    return send_task(payload, task_id)
