"""영수증 처리 Celery 태스크.

idempotency 보장 전략:
1. Redis 락: 동일 파일의 동시 처리 방지 (dispatch 단계)
2. DB 상태 체크: 이미 완료된 영수증 재처리 방지 (task 실행 단계)
3. acks_late=True: worker 장애 시 재큐잉 → 위 두 체크로 안전하게 재처리
"""

import asyncio
import logging
from datetime import UTC, datetime

from sqlalchemy import select

from tax_copilot.agents.graph import build_graph, generate_thread_id
from tax_copilot.agents.state import AgentState
from tax_copilot.core.config import settings
from tax_copilot.core.exceptions import DuplicateReceiptError
from tax_copilot.infra.cache.redis_lock import acquire_lock, release_lock
from tax_copilot.infra.database import AsyncSessionLocal
from tax_copilot.infra.db.models.receipt import (
    STATUS_APPROVED,
    STATUS_FAILED,
    STATUS_NEEDS_REVIEW,
    STATUS_PROCESSING,
    STATUS_REJECTED,
    Receipt,
)
from tax_copilot.workers.celery_app import celery_app

logger = logging.getLogger(__name__)

_TERMINAL_STATUSES = {STATUS_APPROVED, STATUS_NEEDS_REVIEW, STATUS_FAILED, STATUS_REJECTED}
_LOCK_TTL = 300  # 5분


@celery_app.task(
    name="tax_copilot.workers.tasks.receipts.process_receipt",
    acks_late=True,
    reject_on_worker_lost=True,
    bind=True,
)
def process_receipt_task(
    self,
    *,
    tenant_id: int,
    receipt_id: int,
    file_path: str,
    file_hash: str,
    attempt_number: int = 1,
) -> dict:
    """영수증 처리 태스크. Celery는 sync이므로 asyncio.run()으로 async 코드를 실행한다."""
    return asyncio.run(
        _process_async(
            tenant_id=tenant_id,
            receipt_id=receipt_id,
            file_path=file_path,
            file_hash=file_hash,
            attempt_number=attempt_number,
        )
    )


async def _process_async(
    *,
    tenant_id: int,
    receipt_id: int,
    file_path: str,
    file_hash: str,
    attempt_number: int,
) -> dict:
    """실제 처리 로직: DB 상태 확인 → LangGraph 실행 → DB 업데이트.

    완료 후 Redis 락을 해제해 동일 파일의 재처리를 허용한다.
    """
    lock_key = f"lock:receipt:{tenant_id}:{file_hash}"
    try:
        return await _run_workflow(
            tenant_id=tenant_id,
            receipt_id=receipt_id,
            file_path=file_path,
            file_hash=file_hash,
            attempt_number=attempt_number,
        )
    finally:
        release_lock(lock_key)


async def _run_workflow(
    *,
    tenant_id: int,
    receipt_id: int,
    file_path: str,
    file_hash: str,
    attempt_number: int,
) -> dict:
    # 1. DB 상태 확인 및 PROCESSING으로 업데이트
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Receipt).where(Receipt.id == receipt_id))
        receipt = result.scalar_one_or_none()

        if receipt is None:
            logger.error("receipt_not_found receipt_id=%s", receipt_id)
            return {"status": "error", "reason": "receipt_not_found"}

        # 이미 완료된 영수증은 재처리하지 않는다 (idempotency)
        if receipt.status in _TERMINAL_STATUSES:
            logger.info(
                "receipt_already_processed receipt_id=%s status=%s",
                receipt_id,
                receipt.status,
            )
            return {"status": "skipped", "reason": receipt.status}

        thread_id = generate_thread_id(tenant_id, file_hash, receipt_id, attempt_number)
        receipt.status = STATUS_PROCESSING
        receipt.langgraph_thread_id = thread_id
        receipt.attempt_number = attempt_number
        await db.commit()

    # 2. LangGraph 실행 (PostgreSQL checkpointer로 HITL 상태 보존)
    from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

    async with AsyncPostgresSaver.from_conn_string(settings.checkpointer_url) as checkpointer:
        await checkpointer.setup()
        graph = build_graph(checkpointer=checkpointer)

        initial_state = AgentState(
            tenant_id=tenant_id,
            receipt_id=receipt_id,
            file_path=file_path,
            file_hash=file_hash,
            attempt_number=attempt_number,
            transaction_date=None,
            law_as_of_date=None,
            law_corpus_version="v1",
            image_quality=None,
            parsed_receipt=None,
            retrieval_query=None,
            relevant_laws=[],
            calculation_result=None,
            draft_decision=None,
            final_decision=None,
            requires_human=False,
            error_message=None,
            messages=[],
        )
        config = {"configurable": {"thread_id": thread_id}}
        final_state = await graph.ainvoke(initial_state, config=config)

    # 3. 결과를 DB에 저장
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Receipt).where(Receipt.id == receipt_id))
        receipt = result.scalar_one_or_none()
        if receipt is None:
            return {"status": "error", "reason": "receipt_lost_after_processing"}

        final_decision = final_state.get("final_decision") or {}
        is_interrupted = "__interrupt__" in final_state
        requires_human = final_state.get("requires_human", False)

        if is_interrupted or requires_human:
            receipt.status = STATUS_NEEDS_REVIEW
        elif final_decision:
            receipt.status = STATUS_APPROVED
            receipt.parsed_data = final_decision
            receipt.account_code = final_decision.get("account_code")
            tx_date = final_state.get("transaction_date")
            if tx_date is not None:
                receipt.transaction_date = tx_date
        else:
            receipt.status = STATUS_FAILED
            receipt.error_message = "워크플로우가 결과를 반환하지 않았습니다."

        receipt.updated_at = datetime.now(UTC)
        await db.commit()

    return {"status": receipt.status, "receipt_id": receipt_id}


def dispatch_receipt_task(
    *,
    tenant_id: int,
    receipt_id: int,
    file_path: str,
    file_hash: str,
    attempt_number: int = 1,
) -> str:
    """Redis 락을 획득하고 Celery 태스크를 큐에 넣는다."""
    lock_key = f"lock:receipt:{tenant_id}:{file_hash}"
    if not acquire_lock(lock_key, ttl_seconds=_LOCK_TTL):
        raise DuplicateReceiptError("이미 처리 중인 영수증입니다.")

    try:
        task = process_receipt_task.apply_async(
            kwargs={
                "tenant_id": tenant_id,
                "receipt_id": receipt_id,
                "file_path": file_path,
                "file_hash": file_hash,
                "attempt_number": attempt_number,
            },
        )
    except Exception:
        # 큐잉 실패 시에만 즉시 해제; 성공 시에는 worker(_process_async)가 finally로 해제한다.
        release_lock(lock_key)
        raise

    return task.id
