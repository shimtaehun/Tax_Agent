from typing import Any

from tax_copilot.core.workflows.nodes import resume_after_review, run_until_interrupt
from tax_copilot.workers.celery_app import celery_app


@celery_app.task(  # type: ignore[untyped-decorator]
    name="tax_copilot.process_receipt",
    bind=True,
    acks_late=True,
    reject_on_worker_lost=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_kwargs={"max_retries": 3},
)
def process_receipt_task(self: object, **payload: Any) -> dict[str, Any]:
    state = run_until_interrupt(
        {
            "tenant_id": int(payload["tenant_id"]),
            "receipt_id": int(payload["receipt_id"]),
            "file_path": str(payload["file_path"]),
            "file_hash": str(payload["file_hash"]),
            "attempt_number": int(payload.get("attempt_number", 1)),
            "status": "PENDING",
        }
    )
    if state.get("requires_human"):
        return {"status": state["status"], "requires_human": True}
    final_state = resume_after_review(state, {"approved": True, "comment": "auto"})
    return {"status": final_state["status"], "requires_human": False}
