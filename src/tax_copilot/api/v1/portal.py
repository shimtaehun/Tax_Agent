from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from tax_copilot.api.deps import CurrentUser, get_current_user, get_db
from tax_copilot.core.exceptions import AuthorizationError
from tax_copilot.infra.db.models.receipt import Receipt
from tax_copilot.infra.db.models.user import ROLE_CLIENT
from tax_copilot.schemas.portal import PortalDashboardResponse
from tax_copilot.schemas.receipts import ReceiptStatusResponse

router = APIRouter(prefix="/portal", tags=["portal"])

_RECENT_LIMIT = 5


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


@router.get("/dashboard", response_model=PortalDashboardResponse)
async def get_portal_dashboard(
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PortalDashboardResponse:
    """고객사 대시보드 — 영수증 status 집계 + 최근 5건. client 역할 전용."""
    if current_user.role != ROLE_CLIENT:
        raise AuthorizationError("고객사 포털은 client 역할만 접근할 수 있습니다.")
    if current_user.client_company_id is None:
        raise AuthorizationError("client 계정에 고객사가 연결되어 있지 않습니다.")

    company_id = current_user.client_company_id
    base_where = [
        Receipt.tenant_id == current_user.tenant_id,
        Receipt.client_company_id == company_id,
    ]

    # 전체 건수 + status별 집계
    count_rows = await db.execute(
        select(Receipt.status, func.count().label("cnt"))
        .where(*base_where)
        .group_by(Receipt.status)
    )
    by_status: dict[str, int] = {}
    total = 0
    for row in count_rows:
        by_status[row.status] = row.cnt
        total += row.cnt

    # 최근 5건
    recent_result = await db.execute(
        select(Receipt).where(*base_where).order_by(Receipt.created_at.desc()).limit(_RECENT_LIMIT)
    )
    recent = recent_result.scalars().all()

    return PortalDashboardResponse(
        client_company_id=company_id,
        total=total,
        by_status=by_status,
        recent_receipts=[_to_status_response(r) for r in recent],
    )
