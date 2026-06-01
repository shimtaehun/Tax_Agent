import asyncio
import csv
import io
import json
import uuid

import structlog
from fastapi import APIRouter, Depends, Query, UploadFile
from fastapi.responses import Response, StreamingResponse
from sqlalchemy import delete as sql_delete
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from tax_copilot.api.deps import CurrentUser, get_current_user, get_db
from tax_copilot.audit.events import record_event
from tax_copilot.auth.permissions import require_staff_or_admin
from tax_copilot.core.exceptions import AuthorizationError, DuplicateReceiptError, ValidationError
from tax_copilot.core.receipts.validation import compute_file_hash, validate_receipt_file
from tax_copilot.infra.cache.redis_lock import release_lock
from tax_copilot.infra.database import AsyncSessionLocal
from tax_copilot.infra.db.models.audit_event import (
    ACCOUNT_CODE_UPDATED,
    RECEIPT_RETRY_REQUESTED,
    RECEIPT_UPLOADED,
    AuditEvent,
)
from tax_copilot.infra.db.models.client_company import ClientCompany
from tax_copilot.infra.db.models.receipt import (
    STATUS_FAILED,
    STATUS_PENDING,
    STATUS_PROCESSING,
    Receipt,
)
from tax_copilot.infra.db.models.receipt_comment import ReceiptComment
from tax_copilot.infra.db.models.user import ROLE_CLIENT
from tax_copilot.infra.storage.local import save_receipt
from tax_copilot.schemas.comments import (
    CommentCreateRequest,
    CommentListResponse,
    CommentResponse,
)
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
    ReviewUpdateRequest,
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
    if current_user.role == ROLE_CLIENT:
        if current_user.client_company_id is None:
            raise AuthorizationError("client 계정에 고객사가 연결되어 있지 않습니다.")
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


async def _resolve_client_company_id(
    current_user: CurrentUser, param: int | None, db: AsyncSession
) -> int:
    """업로드 요청의 client_company_id를 결정한다.

    client 역할: JWT 클레임에서 자동 추출 (파라미터 무시).
    staff/admin: 요청 파라미터 필수.
    """
    if current_user.role == ROLE_CLIENT:
        if current_user.client_company_id is None:
            raise AuthorizationError("client 계정에 고객사가 연결되어 있지 않습니다.")
        return current_user.client_company_id
    # staff / admin
    if param is None:
        raise ValidationError("client_company_id가 필요합니다.")
    result = await db.execute(
        select(ClientCompany.id).where(
            ClientCompany.id == param,
            ClientCompany.tenant_id == current_user.tenant_id,
            ClientCompany.is_active.is_(True),
        )
    )
    if result.scalar_one_or_none() is None:
        raise ValidationError("유효한 고객사를 찾을 수 없습니다.")
    return param


@router.post("", response_model=ReceiptUploadResponse, status_code=201)
async def upload_receipt(
    file: UploadFile,
    client_company_id: int | None = None,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ReceiptUploadResponse:
    """영수증 파일을 업로드하고 처리 대기 상태로 저장한다."""
    resolved_company_id = await _resolve_client_company_id(current_user, client_company_id, db)

    if file.filename is None:
        raise ValidationError("파일명이 없습니다.")

    content = await file.read()
    mime = validate_receipt_file(file.filename, content)
    file_hash = compute_file_hash(content)

    # 동일 tenant에서 같은 파일 중복 업로드 방지
    existing_result = await db.execute(
        select(Receipt).where(
            Receipt.tenant_id == current_user.tenant_id,
            Receipt.file_hash == file_hash,
        )
    )
    existing_receipt = existing_result.scalar_one_or_none()
    if existing_receipt is not None:
        if existing_receipt.status == STATUS_FAILED:
            # FAILED 영수증은 새 레코드 대신 기존 레코드를 재처리
            next_attempt = existing_receipt.attempt_number + 1
            existing_receipt.status = STATUS_PENDING
            existing_receipt.attempt_number = next_attempt
            existing_receipt.error_message = None
            await db.commit()
            try:
                dispatch_receipt_task(
                    tenant_id=current_user.tenant_id,
                    receipt_id=existing_receipt.id,
                    file_path=existing_receipt.file_path,
                    file_hash=file_hash,
                    attempt_number=next_attempt,
                )
            except Exception:
                logger.exception("receipt.redispatch_failed", receipt_id=existing_receipt.id)
            return ReceiptUploadResponse(
                receipt_id=existing_receipt.id,
                status=STATUS_PENDING,
                message="이전에 실패한 영수증을 재처리합니다.",
            )
        raise DuplicateReceiptError("이미 처리된 영수증입니다.")

    ext = file.filename.rsplit(".", 1)[-1].lower()
    file_path = save_receipt(current_user.tenant_id, file_hash, ext, content)

    receipt = Receipt(
        tenant_id=current_user.tenant_id,
        client_company_id=resolved_company_id,
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
            "client_company_id": resolved_company_id,
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
    if current_user.role == ROLE_CLIENT:
        if current_user.client_company_id is None:
            raise AuthorizationError("client 계정에 고객사가 연결되어 있지 않습니다.")
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
    require_staff_or_admin(current_user.role)

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
    client_company_id: int | None = None,
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

    resolved_company_id = await _resolve_client_company_id(current_user, client_company_id, db)

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
                client_company_id=resolved_company_id,
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
                    "client_company_id": resolved_company_id,
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
    _check_receipt_access(receipt, current_user)

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
            if not c.get("effective_from"):
                continue
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
) -> Response:
    """영수증 처리 상태를 SSE로 스트리밍한다.

    처리 완료(터미널 상태) 또는 최대 2분 경과 시 스트림을 닫는다.
    """

    async def generate():  # type: ignore[return]
        last_status = None
        for _ in range(_SSE_MAX_POLLS):
            async with AsyncSessionLocal() as db:
                receipt = await db.get(Receipt, receipt_id)

            if receipt is None or receipt.tenant_id != current_user.tenant_id:
                return
            if (
                current_user.role == ROLE_CLIENT
                and receipt.client_company_id != current_user.client_company_id
            ):
                return

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


def _check_receipt_access(receipt: Receipt | None, current_user: CurrentUser) -> Receipt:
    """영수증이 존재하는지, client 역할이면 자기 회사 소속인지 확인한다."""
    if receipt is None:
        raise ValidationError("영수증을 찾을 수 없습니다.")
    if current_user.role == ROLE_CLIENT:
        if current_user.client_company_id is None:
            raise AuthorizationError("client 계정에 고객사가 연결되어 있지 않습니다.")
        if receipt.client_company_id != current_user.client_company_id:
            raise ValidationError("영수증을 찾을 수 없습니다.")
    return receipt


@router.get("/{receipt_id}/comments", response_model=CommentListResponse)
async def list_comments(
    receipt_id: int,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CommentListResponse:
    """영수증 코멘트 목록을 반환한다."""
    receipt_result = await db.execute(
        select(Receipt).where(
            Receipt.id == receipt_id,
            Receipt.tenant_id == current_user.tenant_id,
        )
    )
    _check_receipt_access(receipt_result.scalar_one_or_none(), current_user)

    comments_result = await db.execute(
        select(ReceiptComment)
        .where(ReceiptComment.receipt_id == receipt_id)
        .order_by(ReceiptComment.created_at)
    )
    comments = comments_result.scalars().all()

    return CommentListResponse(
        items=[
            CommentResponse(
                id=c.id,
                receipt_id=c.receipt_id,
                author_id=c.author_id,
                body=c.body,
                created_at=c.created_at,
            )
            for c in comments
        ]
    )


@router.post("/{receipt_id}/comments", response_model=CommentResponse, status_code=201)
async def create_comment(
    receipt_id: int,
    body: CommentCreateRequest,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CommentResponse:
    """영수증에 코멘트를 작성한다."""
    receipt_result = await db.execute(
        select(Receipt).where(
            Receipt.id == receipt_id,
            Receipt.tenant_id == current_user.tenant_id,
        )
    )
    _check_receipt_access(receipt_result.scalar_one_or_none(), current_user)

    comment = ReceiptComment(
        receipt_id=receipt_id,
        author_id=current_user.user_id,
        body=body.body,
    )
    db.add(comment)
    await db.flush()
    await db.commit()
    await db.refresh(comment)

    logger.info("comment.created", receipt_id=receipt_id, author_id=current_user.user_id)

    return CommentResponse(
        id=comment.id,
        receipt_id=comment.receipt_id,
        author_id=comment.author_id,
        body=comment.body,
        created_at=comment.created_at,
    )


@router.patch("/{receipt_id}/review", response_model=ReceiptStatusResponse)
async def update_review_info(
    receipt_id: int,
    body: ReviewUpdateRequest,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ReceiptStatusResponse:
    """계정과목 또는 검토 의견을 수정한다. staff/admin 전용."""
    require_staff_or_admin(current_user.role)

    result = await db.execute(
        select(Receipt).where(
            Receipt.id == receipt_id,
            Receipt.tenant_id == current_user.tenant_id,
        )
    )
    receipt = result.scalar_one_or_none()
    if receipt is None:
        raise ValidationError(f"영수증 {receipt_id}를 찾을 수 없습니다.")

    if body.account_code is not None:
        receipt.account_code = body.account_code
    if body.review_comment is not None:
        receipt.review_comment = body.review_comment

    await db.commit()
    await db.refresh(receipt)

    logger.info("receipt.review_updated", receipt_id=receipt_id, actor=current_user.user_id)
    return _to_status_response(receipt)


@router.delete("/{receipt_id}", status_code=204)
async def delete_receipt(
    receipt_id: int,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """영수증을 삭제한다. 관련 코멘트도 함께 삭제. staff/admin 전용."""
    require_staff_or_admin(current_user.role)

    result = await db.execute(
        select(Receipt).where(
            Receipt.id == receipt_id,
            Receipt.tenant_id == current_user.tenant_id,
        )
    )
    receipt = result.scalar_one_or_none()
    if receipt is None:
        raise ValidationError(f"영수증 {receipt_id}를 찾을 수 없습니다.")

    # FK 제약 처리: 코멘트 삭제, 감사 이벤트는 receipt_id를 NULL로
    await db.execute(sql_delete(ReceiptComment).where(ReceiptComment.receipt_id == receipt_id))
    await db.execute(
        update(AuditEvent).where(AuditEvent.receipt_id == receipt_id).values(receipt_id=None)
    )
    await db.delete(receipt)
    await db.commit()

    logger.info("receipt.deleted", receipt_id=receipt_id, actor=current_user.user_id)


@router.post("/{receipt_id}/retry", response_model=ReceiptStatusResponse)
async def retry_receipt_processing(
    receipt_id: int,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ReceiptStatusResponse:
    """실패 또는 대기 중인 영수증 처리를 다시 큐에 넣는다. staff/admin 전용."""
    require_staff_or_admin(current_user.role)

    result = await db.execute(
        select(Receipt).where(
            Receipt.id == receipt_id,
            Receipt.tenant_id == current_user.tenant_id,
        )
    )
    receipt = result.scalar_one_or_none()
    if receipt is None:
        raise ValidationError(f"영수증 {receipt_id}를 찾을 수 없습니다.")
    if receipt.status == STATUS_PROCESSING:
        raise ValidationError("이미 처리 중인 영수증입니다.")

    previous_status = receipt.status
    next_attempt = receipt.attempt_number + 1
    receipt.status = STATUS_PENDING
    receipt.attempt_number = next_attempt
    receipt.error_message = None

    await record_event(
        db,
        tenant_id=current_user.tenant_id,
        event_type=RECEIPT_RETRY_REQUESTED,
        actor_user_id=current_user.user_id,
        receipt_id=receipt.id,
        payload={"attempt_number": next_attempt, "previous_status": previous_status},
    )
    await db.commit()

    try:
        task_id = dispatch_receipt_task(
            tenant_id=current_user.tenant_id,
            receipt_id=receipt.id,
            file_path=receipt.file_path,
            file_hash=receipt.file_hash,
            attempt_number=next_attempt,
        )
        await db.execute(
            update(Receipt).where(Receipt.id == receipt.id).values(celery_task_id=task_id)
        )
        await db.commit()
    except DuplicateReceiptError:
        logger.warning("receipt.retry_duplicate", receipt_id=receipt.id)
    except Exception:
        receipt.status = STATUS_FAILED
        receipt.error_message = "재처리 큐 등록에 실패했습니다."
        await db.commit()
        logger.exception("receipt.retry_dispatch_failed", receipt_id=receipt.id)

    await db.refresh(receipt)
    return _to_status_response(receipt)


@router.post("/{receipt_id}/cancel", response_model=ReceiptStatusResponse)
async def cancel_receipt_processing(
    receipt_id: int,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ReceiptStatusResponse:
    """대기 중이거나 처리 중인 영수증을 취소한다. staff/admin 전용."""
    require_staff_or_admin(current_user.role)

    result = await db.execute(
        select(Receipt).where(
            Receipt.id == receipt_id,
            Receipt.tenant_id == current_user.tenant_id,
        )
    )
    receipt = result.scalar_one_or_none()
    if receipt is None:
        raise ValidationError(f"영수증 {receipt_id}를 찾을 수 없습니다.")
    if receipt.status not in (STATUS_PENDING, STATUS_PROCESSING):
        raise ValidationError("대기 중이거나 처리 중인 영수증만 취소할 수 있습니다.")

    # Celery 태스크 취소 시도
    if receipt.celery_task_id:
        try:
            from tax_copilot.workers.celery_app import celery_app

            celery_app.control.revoke(receipt.celery_task_id, terminate=True)
        except Exception:
            logger.warning("receipt.cancel_revoke_failed", receipt_id=receipt_id)

    # Redis 락 해제
    lock_key = f"lock:receipt:{receipt.tenant_id}:{receipt.file_hash}"
    release_lock(lock_key)

    receipt.status = STATUS_FAILED
    receipt.error_message = "사용자가 처리를 취소했습니다."
    await db.commit()
    await db.refresh(receipt)

    logger.info("receipt.cancelled", receipt_id=receipt_id, actor=current_user.user_id)
    return _to_status_response(receipt)


@router.get("/{receipt_id}/audit.csv")
async def export_receipt_audit_csv(
    receipt_id: int,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    """영수증 감사 로그를 CSV로 내려받는다."""
    result = await db.execute(
        select(Receipt).where(
            Receipt.id == receipt_id,
            Receipt.tenant_id == current_user.tenant_id,
        )
    )
    receipt = _check_receipt_access(result.scalar_one_or_none(), current_user)

    events_result = await db.execute(
        select(AuditEvent)
        .where(
            AuditEvent.receipt_id == receipt.id,
            AuditEvent.tenant_id == current_user.tenant_id,
        )
        .order_by(AuditEvent.created_at)
    )
    events = events_result.scalars().all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["created_at", "event_type", "actor_user_id", "payload"])
    for event in events:
        writer.writerow(
            [
                event.created_at.isoformat(),
                event.event_type,
                event.actor_user_id or "",
                json.dumps(event.payload or {}, ensure_ascii=False),
            ]
        )
    output.seek(0)

    headers = {"Content-Disposition": f'attachment; filename="receipt-{receipt.id}-audit.csv"'}
    return Response(content=output.getvalue(), media_type="text/csv", headers=headers)
