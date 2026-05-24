import asyncio
import json
import uuid

import structlog
from fastapi import APIRouter, Depends, Query, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from tax_copilot.api.deps import CurrentUser, get_current_user, get_db
from tax_copilot.audit.events import record_event
from tax_copilot.core.exceptions import DuplicateReceiptError, ValidationError
from tax_copilot.core.receipts.validation import compute_file_hash, validate_receipt_file
from tax_copilot.infra.database import AsyncSessionLocal
from tax_copilot.infra.db.models.audit_event import (
    ACCOUNT_CODE_UPDATED,
    RECEIPT_UPLOADED,
    AuditEvent,
)
from tax_copilot.infra.db.models.receipt import STATUS_PENDING, Receipt
from tax_copilot.infra.db.models.user import ROLE_CLIENT
from tax_copilot.infra.storage.local import save_receipt
from tax_copilot.schemas.explanation import (
    AuditEvent as AuditEventSchema,
)
from tax_copilot.schemas.explanation import (
    CitationResponse,
    DecisionSummary,
    ExplanationResponse,
)
from tax_copilot.schemas.receipts import (
    AccountCodeUpdateRequest,
    BatchReceiptResult,
    BatchUploadResponse,
    ReceiptListResponse,
    ReceiptStatusResponse,
    ReceiptUploadResponse,
)
from tax_copilot.workers.tasks.receipts import dispatch_receipt_task

_BATCH_MAX_FILES = 20

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/receipts", tags=["receipts"])


def _to_status_response(r: Receipt) -> ReceiptStatusResponse:
    return ReceiptStatusResponse(
        receipt_id=r.id,
        status=r.status,
        original_filename=r.original_filename,
        mime_type=r.mime_type,
        file_size_bytes=r.file_size_bytes,
        client_company_id=r.client_company_id,
        uploaded_by=r.uploaded_by,
        transaction_date=r.transaction_date,
        parsed_data=r.parsed_data,
        langgraph_thread_id=r.langgraph_thread_id,
        attempt_number=r.attempt_number,
        error_message=r.error_message,
        reviewed_by=r.reviewed_by,
        reviewed_at=r.reviewed_at,
        review_comment=r.review_comment,
        account_code=r.account_code,
        account_code_reason=r.parsed_data.get("account_code_reason") if r.parsed_data else None,
        duplicate_suspect=r.duplicate_suspect,
        duplicate_receipt_ids=r.duplicate_receipt_ids or [],
        created_at=r.created_at,
        updated_at=r.updated_at,
    )


@router.get("", response_model=ReceiptListResponse)
async def list_receipts(
    status: str | None = Query(
        default=None,
        description="상태 필터 (PENDING, PROCESSING, NEEDS_REVIEW, APPROVED, REJECTED, FAILED)",
    ),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ReceiptListResponse:
    """영수증 목록을 조회한다. status로 필터링 가능."""
    base_where = [Receipt.tenant_id == current_user.tenant_id]
    # client 역할은 자신의 고객사 영수증만 조회 가능
    if current_user.role == ROLE_CLIENT and current_user.client_company_id is not None:
        base_where.append(Receipt.client_company_id == current_user.client_company_id)
    if status:
        base_where.append(Receipt.status == status)

    total_result = await db.execute(select(func.count()).select_from(Receipt).where(*base_where))
    total = total_result.scalar_one()

    result = await db.execute(
        select(Receipt)
        .where(*base_where)
        .order_by(Receipt.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    receipts = result.scalars().all()

    return ReceiptListResponse(
        items=[_to_status_response(r) for r in receipts],
        total=total,
    )


@router.post("", response_model=ReceiptUploadResponse, status_code=201)
async def upload_receipt(
    file: UploadFile,
    client_company_id: int,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ReceiptUploadResponse:
    """영수증 파일을 업로드하고 처리 대기 상태로 저장한다."""
    if file.filename is None:
        raise ValidationError("파일명이 없습니다.")

    content = await file.read()
    mime = validate_receipt_file(file.filename, content)
    file_hash = compute_file_hash(content)

    # 동일 tenant에서 같은 파일 중복 업로드 방지
    existing = await db.execute(
        select(Receipt).where(
            Receipt.tenant_id == current_user.tenant_id,
            Receipt.file_hash == file_hash,
        )
    )
    if existing.scalar_one_or_none() is not None:
        raise DuplicateReceiptError("이미 처리된 영수증입니다.")

    ext = file.filename.rsplit(".", 1)[-1].lower()
    file_path = save_receipt(current_user.tenant_id, file_hash, ext, content)

    receipt = Receipt(
        tenant_id=current_user.tenant_id,
        client_company_id=client_company_id,
        uploaded_by=current_user.user_id,
        file_path=file_path,
        file_hash=file_hash,
        original_filename=file.filename,
        mime_type=mime,
        file_size_bytes=len(content),
        status=STATUS_PENDING,
    )
    db.add(receipt)
    await db.flush()  # id 확보

    await record_event(
        db,
        tenant_id=current_user.tenant_id,
        event_type=RECEIPT_UPLOADED,
        actor_user_id=current_user.user_id,
        receipt_id=receipt.id,
        payload={
            "filename": file.filename,
            "mime_type": mime,
            "file_size_bytes": len(content),
            "client_company_id": client_company_id,
        },
    )

    await db.commit()

    # Celery 태스크 디스패치 (DB 커밋 이후 — receipt가 DB에 확정된 상태)
    task_id: str | None = None
    try:
        task_id = dispatch_receipt_task(
            tenant_id=current_user.tenant_id,
            receipt_id=receipt.id,
            file_path=file_path,
            file_hash=file_hash,
        )
        # celery_task_id를 별도 UPDATE로 저장 (커밋된 row를 수정)
        await db.execute(
            update(Receipt).where(Receipt.id == receipt.id).values(celery_task_id=task_id)
        )
        await db.commit()
    except DuplicateReceiptError:
        # Redis 락 경합은 DB 수준에서 이미 막혔으나 방어적으로 처리
        logger.warning("receipt.dispatch_duplicate", receipt_id=receipt.id)
    except Exception:
        # Celery/Redis 장애 시 receipt는 PENDING 상태로 유지 — 수동 재처리 가능
        logger.exception("receipt.dispatch_failed", receipt_id=receipt.id)

    logger.info(
        "receipt.uploaded",
        tenant_id=current_user.tenant_id,
        receipt_id=receipt.id,
        file_size_bytes=len(content),
        celery_task_id=task_id,
    )

    return ReceiptUploadResponse(
        receipt_id=receipt.id,
        status=STATUS_PENDING,
        message="영수증이 업로드되었습니다. 처리가 시작될 예정입니다.",
    )


@router.get("/{receipt_id}", response_model=ReceiptStatusResponse)
async def get_receipt_status(
    receipt_id: int,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ReceiptStatusResponse:
    """영수증 처리 상태를 조회한다."""
    filters = [Receipt.id == receipt_id, Receipt.tenant_id == current_user.tenant_id]
    if current_user.role == ROLE_CLIENT and current_user.client_company_id is not None:
        filters.append(Receipt.client_company_id == current_user.client_company_id)
    result = await db.execute(select(Receipt).where(*filters))
    receipt = result.scalar_one_or_none()
    if receipt is None:
        raise ValidationError(f"영수증 {receipt_id}를 찾을 수 없습니다.")

    return _to_status_response(receipt)


@router.patch("/{receipt_id}/account-code", response_model=ReceiptStatusResponse)
async def update_account_code(
    receipt_id: int,
    body: AccountCodeUpdateRequest,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ReceiptStatusResponse:
    """세무사가 계정과목을 직접 수정 확정한다."""
    result = await db.execute(
        select(Receipt).where(
            Receipt.id == receipt_id,
            Receipt.tenant_id == current_user.tenant_id,
        )
    )
    receipt = result.scalar_one_or_none()
    if receipt is None:
        raise ValidationError(f"영수증 {receipt_id}를 찾을 수 없습니다.")

    old_code = receipt.account_code
    receipt.account_code = body.account_code

    await record_event(
        db,
        tenant_id=current_user.tenant_id,
        event_type=ACCOUNT_CODE_UPDATED,
        actor_user_id=current_user.user_id,
        receipt_id=receipt.id,
        payload={"old": old_code, "new": body.account_code},
    )

    await db.commit()
    await db.refresh(receipt)

    logger.info(
        "receipt.account_code_updated",
        receipt_id=receipt_id,
        old=old_code,
        new=body.account_code,
    )
    return _to_status_response(receipt)


@router.post("/batch", response_model=BatchUploadResponse, status_code=201)
async def batch_upload_receipts(
    files: list[UploadFile],
    client_company_id: int,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> BatchUploadResponse:
    """최대 20개 파일을 한 번에 업로드한다.

    파일별로 독립적으로 처리한다:
    - 중복 파일은 skipped 처리 (전체 배치를 실패시키지 않음)
    - 유효하지 않은 파일은 error 처리
    """
    if len(files) > _BATCH_MAX_FILES:
        raise ValidationError(f"한 번에 최대 {_BATCH_MAX_FILES}개까지 업로드할 수 있습니다.")

    batch_id = str(uuid.uuid4())
    results: list[BatchReceiptResult] = []
    # 커밋 후 Celery 디스패치에 필요한 정보를 추적
    dispatch_queue: list[tuple[int, str, str]] = []  # (receipt_id, file_path, file_hash)

    for file in files:
        filename = file.filename or "unknown"
        try:
            content = await file.read()
            mime = validate_receipt_file(filename, content)
            file_hash = compute_file_hash(content)

            existing = await db.execute(
                select(Receipt).where(
                    Receipt.tenant_id == current_user.tenant_id,
                    Receipt.file_hash == file_hash,
                )
            )
            if existing.scalar_one_or_none() is not None:
                results.append(
                    BatchReceiptResult(filename=filename, status="skipped", reason="중복 파일")
                )
                continue

            ext = filename.rsplit(".", 1)[-1].lower()
            file_path = save_receipt(current_user.tenant_id, file_hash, ext, content)

            receipt = Receipt(
                tenant_id=current_user.tenant_id,
                client_company_id=client_company_id,
                uploaded_by=current_user.user_id,
                file_path=file_path,
                file_hash=file_hash,
                original_filename=filename,
                mime_type=mime,
                file_size_bytes=len(content),
                status=STATUS_PENDING,
                batch_id=batch_id,
            )
            db.add(receipt)
            await db.flush()

            await record_event(
                db,
                tenant_id=current_user.tenant_id,
                event_type=RECEIPT_UPLOADED,
                actor_user_id=current_user.user_id,
                receipt_id=receipt.id,
                payload={
                    "filename": filename,
                    "mime_type": mime,
                    "file_size_bytes": len(content),
                    "client_company_id": client_company_id,
                    "batch_id": batch_id,
                },
            )

            results.append(
                BatchReceiptResult(filename=filename, receipt_id=receipt.id, status="queued")
            )
            dispatch_queue.append((receipt.id, file_path, file_hash))

        except Exception as exc:
            results.append(BatchReceiptResult(filename=filename, status="error", reason=str(exc)))

    await db.commit()

    # Celery 태스크 디스패치 (커밋 이후)
    for receipt_id, file_path, file_hash in dispatch_queue:
        try:
            dispatch_receipt_task(
                tenant_id=current_user.tenant_id,
                receipt_id=receipt_id,
                file_path=file_path,
                file_hash=file_hash,
            )
        except Exception:
            logger.exception("batch.dispatch_failed", receipt_id=receipt_id)

    queued = sum(1 for r in results if r.status == "queued")
    skipped = sum(1 for r in results if r.status == "skipped")
    errors = sum(1 for r in results if r.status == "error")

    logger.info(
        "batch.uploaded",
        batch_id=batch_id,
        total=len(files),
        queued=queued,
        skipped=skipped,
        errors=errors,
    )

    return BatchUploadResponse(
        batch_id=batch_id,
        total=len(files),
        queued_count=queued,
        skipped_count=skipped,
        error_count=errors,
        results=results,
    )


@router.get("/{receipt_id}/explanation", response_model=ExplanationResponse)
async def get_receipt_explanation(
    receipt_id: int,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ExplanationResponse:
    """영수증 판단 근거 및 처리 이력을 반환한다."""
    result = await db.execute(
        select(Receipt).where(
            Receipt.id == receipt_id,
            Receipt.tenant_id == current_user.tenant_id,
        )
    )
    receipt = result.scalar_one_or_none()
    if receipt is None:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="영수증을 찾을 수 없습니다.")

    # 감사 이벤트 조회
    events_result = await db.execute(
        select(AuditEvent)
        .where(
            AuditEvent.receipt_id == receipt_id,
            AuditEvent.tenant_id == current_user.tenant_id,
        )
        .order_by(AuditEvent.created_at)
    )
    events = events_result.scalars().all()

    parsed = receipt.parsed_data or {}

    decision: DecisionSummary | None = None
    citations: list[CitationResponse] = []
    risk_flags: list[str] = []

    if parsed:
        decision = DecisionSummary(
            vat_creditable=parsed.get("vat_creditable"),
            expense_deductible=parsed.get("expense_deductible"),
            account_code=parsed.get("account_code"),
            account_code_reason=parsed.get("account_code_reason"),
            evidence_type=parsed.get("evidence_type", "unknown"),
            evidence_status=parsed.get("evidence_status", "unknown"),
            confidence=float(parsed.get("confidence", 0.0)),
            prompt_version=str(parsed.get("prompt_version", "")),
            model_name=str(parsed.get("model_name", "")),
            law_corpus_version=str(parsed.get("law_corpus_version", "")),
            calculation_result=parsed.get("calculation_result"),
            human_approved=parsed.get("human_approved"),
            human_comment=parsed.get("human_comment"),
        )
        for c in parsed.get("citations", []):
            citations.append(
                CitationResponse(
                    chunk_id=c.get("chunk_id", ""),
                    law_name=c.get("law_name", ""),
                    article_no=c.get("article_no"),
                    paragraph_no=c.get("paragraph_no"),
                    effective_from=c["effective_from"],
                    effective_to=c.get("effective_to"),
                    quoted_text=c.get("quoted_text", ""),
                )
            )
        risk_flags = list(parsed.get("risk_flags", []))

    return ExplanationResponse(
        receipt_id=receipt_id,
        status=receipt.status,
        decision=decision,
        citations=citations,
        risk_flags=risk_flags,
        audit_trail=[
            AuditEventSchema(
                event_type=e.event_type,
                actor_user_id=e.actor_user_id,
                created_at=e.created_at,
                payload=e.payload,
            )
            for e in events
        ],
    )


_SSE_TERMINAL_STATUSES = {"APPROVED", "NEEDS_REVIEW", "FAILED", "REJECTED"}
_SSE_POLL_INTERVAL = 2  # 초
_SSE_MAX_POLLS = 60  # 최대 2분


@router.get("/{receipt_id}/events")
async def receipt_status_events(
    receipt_id: int,
    current_user: CurrentUser = Depends(get_current_user),
) -> StreamingResponse:
    """영수증 처리 상태를 SSE로 스트리밍한다.

    처리 완료(터미널 상태) 또는 최대 2분 경과 시 스트림을 닫는다.
    """

    async def generate():  # type: ignore[return]
        last_status = None
        for _ in range(_SSE_MAX_POLLS):
            async with AsyncSessionLocal() as db:
                receipt = await db.get(Receipt, receipt_id)

            if receipt is None or receipt.tenant_id != current_user.tenant_id:
                break

            if receipt.status != last_status:
                last_status = receipt.status
                data = json.dumps({"receipt_id": receipt_id, "status": receipt.status})
                yield f"data: {data}\n\n"

            if receipt.status in _SSE_TERMINAL_STATUSES:
                yield "event: done\ndata: {}\n\n"
                return

            await asyncio.sleep(_SSE_POLL_INTERVAL)

        yield "event: timeout\ndata: {}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")
