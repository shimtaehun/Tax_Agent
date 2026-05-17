import pytest

from tax_copilot.core.exceptions import DuplicateReceiptError
from tax_copilot.core.tasks import InMemoryReceiptLock, ReceiptTaskPayload, dispatch_receipt_task
from tax_copilot.core.tasks.receipts import build_receipt_task_id


def _payload() -> ReceiptTaskPayload:
    return ReceiptTaskPayload(
        tenant_id=1,
        receipt_id=10,
        file_path="local://receipt.png",
        file_hash="abcdef1234567890abcdef1234567890",  # pragma: allowlist secret
        attempt_number=1,
    )


def test_dispatch_receipt_task_uses_deterministic_task_id() -> None:
    lock = InMemoryReceiptLock()
    sent: list[tuple[ReceiptTaskPayload, str]] = []

    def send_task(payload: ReceiptTaskPayload, task_id: str) -> str:
        sent.append((payload, task_id))
        return task_id

    task_id = dispatch_receipt_task(
        _payload(),
        acquire_lock=lock.acquire,
        send_task=send_task,
    )

    assert task_id == "receipt-1-abcdef1234567890-a1"
    assert sent[0][1] == build_receipt_task_id(_payload())


def test_dispatch_receipt_task_blocks_duplicate_in_flight_work() -> None:
    lock = InMemoryReceiptLock()

    def send_task(payload: ReceiptTaskPayload, task_id: str) -> str:
        return task_id

    dispatch_receipt_task(_payload(), acquire_lock=lock.acquire, send_task=send_task)

    with pytest.raises(DuplicateReceiptError):
        dispatch_receipt_task(_payload(), acquire_lock=lock.acquire, send_task=send_task)


def test_process_receipt_task_is_configured_for_late_ack() -> None:
    from tax_copilot.workers.receipts import process_receipt_task

    assert process_receipt_task.acks_late is True
    assert process_receipt_task.reject_on_worker_lost is True
