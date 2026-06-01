"""세금 신고 기한 관리 API."""

from datetime import datetime

import structlog
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from tax_copilot.api.deps import CurrentUser, get_current_user, get_db
from tax_copilot.auth.permissions import require_staff_or_admin
from tax_copilot.core.tax.deadlines import generate_annual_deadlines
from tax_copilot.infra.db.models.filing_deadline import (
    DEADLINE_STATUS_COMPLETED,
    FilingDeadline,
)
from tax_copilot.infra.db.models.user import ROLE_CLIENT
from tax_copilot.schemas.deadlines import (
    DeadlineListResponse,
    FilingDeadlineResponse,
    GenerateDeadlinesRequest,
    GenerateDeadlinesResponse,
)

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/deadlines", tags=["deadlines"])


def _to_response(d: FilingDeadline) -> FilingDeadlineResponse:
    return FilingDeadlineResponse(
        id=d.id,
        client_company_id=d.client_company_id,
        tax_type=d.tax_type,
        fiscal_year=d.fiscal_year,
        due_date=d.due_date,
        description=d.description,
        status=d.status,
        completed_at=d.completed_at,
        completed_by=d.completed_by,
        created_at=d.created_at,
    )


@router.get("", response_model=DeadlineListResponse)
async def list_deadlines(
    client_company_id: int | None = Query(default=None),
    fiscal_year: int | None = Query(default=None),
    status: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> DeadlineListResponse:
    """신고 기한 목록을 조회한다."""
    filters = [FilingDeadline.tenant_id == current_user.tenant_id]
    if current_user.role == ROLE_CLIENT:
        if current_user.client_company_id is None:
            from tax_copilot.core.exceptions import AuthorizationError

            raise AuthorizationError("client 계정에 고객사가 연결되어 있지 않습니다.")
        if client_company_id is not None and client_company_id != current_user.client_company_id:
            from tax_copilot.core.exceptions import AuthorizationError

            raise AuthorizationError("다른 고객사의 신고 기한에 접근할 수 없습니다.")
        filters.append(FilingDeadline.client_company_id == current_user.client_company_id)
    elif client_company_id is not None:
        filters.append(FilingDeadline.client_company_id == client_company_id)
    if fiscal_year is not None:
        filters.append(FilingDeadline.fiscal_year == fiscal_year)
    if status is not None:
        filters.append(FilingDeadline.status == status)

    result = await db.execute(
        select(FilingDeadline).where(*filters).order_by(FilingDeadline.due_date)
    )
    items = result.scalars().all()
    return DeadlineListResponse(items=[_to_response(d) for d in items], total=len(items))


@router.post("/generate", response_model=GenerateDeadlinesResponse, status_code=201)
async def generate_deadlines(
    body: GenerateDeadlinesRequest,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> GenerateDeadlinesResponse:
    """한 해 신고 기한을 일괄 생성한다.

    이미 존재하는 항목은 건너뛴다 (멱등).
    """
    require_staff_or_admin(current_user.role)
    deadlines = generate_annual_deadlines(body.fiscal_year)
    created = 0
    skipped = 0

    for d in deadlines:
        existing = await db.execute(
            select(FilingDeadline).where(
                FilingDeadline.tenant_id == current_user.tenant_id,
                FilingDeadline.client_company_id == body.client_company_id,
                FilingDeadline.fiscal_year == body.fiscal_year,
                FilingDeadline.tax_type == d["tax_type"],
            )
        )
        if existing.scalar_one_or_none() is not None:
            skipped += 1
            continue

        row = FilingDeadline(
            tenant_id=current_user.tenant_id,
            client_company_id=body.client_company_id,
            tax_type=d["tax_type"],
            fiscal_year=d["fiscal_year"],
            due_date=d["due_date"],
            description=d["description"],
        )
        db.add(row)
        try:
            await db.flush()
            created += 1
        except IntegrityError:
            await db.rollback()
            skipped += 1

    await db.commit()
    logger.info(
        "deadlines.generated",
        tenant_id=current_user.tenant_id,
        client_company_id=body.client_company_id,
        fiscal_year=body.fiscal_year,
        created=created,
        skipped=skipped,
    )
    return GenerateDeadlinesResponse(created_count=created, skipped_count=skipped)


@router.post("/{deadline_id}/complete", response_model=FilingDeadlineResponse)
async def complete_deadline(
    deadline_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> FilingDeadlineResponse:
    """신고 완료로 표시한다."""
    require_staff_or_admin(current_user.role)
    result = await db.execute(
        select(FilingDeadline).where(
            FilingDeadline.id == deadline_id,
            FilingDeadline.tenant_id == current_user.tenant_id,
        )
    )
    deadline = result.scalar_one_or_none()
    if deadline is None:
        from tax_copilot.core.exceptions import ValidationError

        raise ValidationError(f"신고 기한 {deadline_id}를 찾을 수 없습니다.")

    deadline.status = DEADLINE_STATUS_COMPLETED
    deadline.completed_at = datetime.utcnow()
    deadline.completed_by = current_user.user_id
    await db.commit()
    await db.refresh(deadline)

    logger.info("deadline.completed", deadline_id=deadline_id, tenant_id=current_user.tenant_id)
    return _to_response(deadline)
