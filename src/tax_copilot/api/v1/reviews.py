"""HITL 검토 API.

세무사가 AI 판단 초안을 승인하거나 반려한다.
"""

from datetime import UTC, datetime

import structlog
from fastapi import APIRouter, Depends, Request
from langgraph.types import Command
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from tax_copilot.api.deps import CurrentUser, get_current_user, get_db
from tax_copilot.audit.events import record_event
from tax_copilot.auth.permissions import require_staff_or_admin
from tax_copilot.core.exceptions import ValidationError
from tax_copilot.infra.db.models.audit_event import HUMAN_REVIEW_APPROVED, HUMAN_REVIEW_REJECTED
from tax_copilot.infra.db.models.receipt import (
    STATUS_APPROVED,
    STATUS_NEEDS_REVIEW,
    STATUS_REJECTED,
    Receipt,
)
from tax_copilot.schemas.reviews import ReviewDecision, ReviewHistoryItem, ReviewItem, ReviewResult

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/reviews", tags=["reviews"])


@router.get("/pending", response_model=list[ReviewItem])
async def list_pending_reviews(
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[ReviewItem]:
    """세무사 검토 대기 중인 영수증 목록을 반환한다."""
    require_staff_or_admin(current_user.role)

    result = await db.execute(
        select(Receipt)
        .where(
            Receipt.tenant_id == current_user.tenant_id,
            Receipt.status == STATUS_NEEDS_REVIEW,
        )
        .order_by(Receipt.created_at.asc())
    )
    receipts = result.scalars().all()

    return [
        ReviewItem(
            receipt_id=r.id,
            original_filename=r.original_filename,
            langgraph_thread_id=r.langgraph_thread_id or "",
            created_at=r.created_at,
        )
        for r in receipts
    ]


@router.get("/history", response_model=list[ReviewHistoryItem])
async def list_review_history(
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[ReviewHistoryItem]:
    """승인 또는 반려된 영수증 목록을 반환한다."""
    require_staff_or_admin(current_user.role)

    result = await db.execute(
        select(Receipt)
        .where(
            Receipt.tenant_id == current_user.tenant_id,
            Receipt.status.in_([STATUS_APPROVED, STATUS_REJECTED]),
        )
        .order_by(Receipt.reviewed_at.desc())
    )
    receipts = result.scalars().all()

    return [
        ReviewHistoryItem(
            receipt_id=r.id,
            original_filename=r.original_filename,
            status=r.status,
            reviewed_by=r.reviewed_by,
            reviewed_at=r.reviewed_at,
            review_comment=r.review_comment,
            transaction_date=str(r.transaction_date) if r.transaction_date else None,
            account_code=r.account_code,
            created_at=r.created_at,
        )
        for r in receipts
    ]


@router.post("/{receipt_id}/decide", response_model=ReviewResult)
async def decide_review(
    receipt_id: int,
    body: ReviewDecision,
    request: Request,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ReviewResult:
    """세무사가 AI 판단 초안을 승인하거나 반려한다."""
    require_staff_or_admin(current_user.role)

    result = await db.execute(
        select(Receipt).where(
            Receipt.id == receipt_id,
            Receipt.tenant_id == current_user.tenant_id,
            Receipt.status == STATUS_NEEDS_REVIEW,
        )
    )
    receipt = result.scalar_one_or_none()
    if receipt is None:
        raise ValidationError(f"검토 대기 중인 영수증 {receipt_id}를 찾을 수 없습니다.")

    thread_id = receipt.langgraph_thread_id
    if not thread_id:
        raise ValidationError("LangGraph thread_id가 없습니다.")

    graph = request.app.state.graph
    config = {"configurable": {"thread_id": thread_id}}

    try:
        await graph.ainvoke(
            Command(resume={"approved": body.approved, "comment": body.comment}),
            config=config,
        )
    except Exception:
        logger.exception("graph.ainvoke_failed", receipt_id=receipt_id, thread_id=thread_id)
        raise ValidationError(  # noqa: E501 (Korean message)
            "워크플로우 재개에 실패했습니다. 잠시 후 다시 시도해주세요."
        ) from None

    new_status = STATUS_APPROVED if body.approved else STATUS_REJECTED
    receipt.status = new_status
    receipt.reviewed_by = current_user.user_id
    receipt.reviewed_at = datetime.now(UTC)
    receipt.review_comment = body.comment
    receipt.updated_at = datetime.now(UTC)

    event_type = HUMAN_REVIEW_APPROVED if body.approved else HUMAN_REVIEW_REJECTED
    await record_event(
        db,
        tenant_id=current_user.tenant_id,
        event_type=event_type,
        actor_user_id=current_user.user_id,
        receipt_id=receipt_id,
        payload={"approved": body.approved, "comment": body.comment},
    )

    await db.commit()

    logger.info(
        "review.decided",
        receipt_id=receipt_id,
        approved=body.approved,
        reviewer=current_user.user_id,
    )

    return ReviewResult(
        receipt_id=receipt_id,
        status=new_status,
        message="승인되었습니다." if body.approved else "반려되었습니다.",
    )
