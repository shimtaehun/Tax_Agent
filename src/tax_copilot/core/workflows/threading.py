from uuid import uuid4


def generate_thread_id(
    tenant_id: int,
    file_hash: str,
    receipt_id: int,
    attempt_number: int,
) -> str:
    suffix = uuid4().hex[:8]
    return f"t{tenant_id}-{file_hash[:8]}-r{receipt_id}-a{attempt_number}-{suffix}"
