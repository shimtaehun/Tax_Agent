import structlog
from fastapi import APIRouter, Depends, Query, UploadFile
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from tax_copilot.api.deps import CurrentUser, get_current_user, get_db
from tax_copilot.audit.events import record_event
from tax_copilot.core.exceptions import DuplicateReceiptError, ValidationError
from tax_copilot.core.receipts.validation import compute_file_hash, validate_receipt_file
from tax_copilot.infra.db.models.audit_event import ACCOUNT_CODE_UPDATED, RECEIPT_UPLOADED
from tax_copilot.infra.db.models.receipt import STATUS_PENDING, Receipt
from tax_copilot.infra.storage.local import save_receipt
from tax_copilot.schemas.receipts import (
    AccountCodeUpdateRequest,
    ReceiptListResponse,
    ReceiptStatusResponse,
    ReceiptUploadResponse,
)
from tax_copilot.workers.tasks.receipts import dispatch_receipt_task

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
    result = await db.execute(
        select(Receipt).where(
            Receipt.id == receipt_id,
            Receipt.tenant_id == current_user.tenant_id,  # tenant 범위 강제
        )
    )
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
