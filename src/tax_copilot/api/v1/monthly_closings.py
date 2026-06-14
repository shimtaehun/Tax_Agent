"""고객사 월마감 체크리스트 API.

매달 반복되는 마감 절차를 표준 템플릿으로 만들고 진행률을 추적한다.
- POST  /monthly-closings                       : 생성(없으면 템플릿으로, 있으면 기존 반환)
- GET   /monthly-closings                       : 목록(고객사/연도 필터)
- GET   /monthly-closings/{id}                  : 단건
- PATCH /monthly-closings/{id}/steps/{step_key} : 단계 완료 토글
"""

from datetime import datetime

import structlog
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from tax_copilot.api.deps import CurrentUser, get_current_user, get_db
from tax_copilot.core.exceptions import AuthorizationError, ValidationError
from tax_copilot.core.tax.monthly_closing import (
    ClosingStep,
    default_steps,
    overall_status,
    progress_ratio,
    set_step_done,
)
from tax_copilot.infra.db.models.monthly_closing import MonthlyClosing
from tax_copilot.infra.db.models.user import ROLE_CLIENT
from tax_copilot.schemas.monthly_closing import (
    ClosingStepOut,
    MonthlyClosingCreate,
    MonthlyClosingListResponse,
    MonthlyClosingOut,
    StepUpdateRequest,
)

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/monthly-closings", tags=["monthly-closings"])


def _ensure_staff(current_user: CurrentUser) -> None:
    if current_user.role == ROLE_CLIENT:
        raise AuthorizationError("고객사 계정은 월마감을 관리할 수 없습니다.")


def _steps_from_db(raw: list[dict] | None) -> list[ClosingStep]:
    return [ClosingStep(**s) for s in (raw or [])]


def _to_out(row: MonthlyClosing) -> MonthlyClosingOut:
    steps = _steps_from_db(row.steps)
    return MonthlyClosingOut(
        id=row.id,
        client_company_id=row.client_company_id,
        year=row.year,
        month=row.month,
        status=row.status,
        progress=round(progress_ratio(steps), 3),
        steps=[ClosingStepOut(**s.model_dump()) for s in steps],
        created_at=row.created_at,
    )


@router.post("", response_model=MonthlyClosingOut)
async def create_closing(
    body: MonthlyClosingCreate,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> MonthlyClosingOut:
    _ensure_staff(current_user)
    if not (1 <= body.month <= 12):
        raise ValidationError("month는 1~12 사이여야 합니다.")

    existing = (
        await db.execute(
            select(MonthlyClosing).where(
                MonthlyClosing.tenant_id == current_user.tenant_id,
                MonthlyClosing.client_company_id == body.client_company_id,
                MonthlyClosing.year == body.year,
                MonthlyClosing.month == body.month,
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        return _to_out(existing)

    steps = default_steps()
    row = MonthlyClosing(
        tenant_id=current_user.tenant_id,
        client_company_id=body.client_company_id,
        created_by=current_user.user_id,
        year=body.year,
        month=body.month,
        steps=[s.model_dump() for s in steps],
        status=overall_status(steps),
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    logger.info(
        "monthly_closing.created",
        tenant_id=current_user.tenant_id,
        client_company_id=body.client_company_id,
        year=body.year,
        month=body.month,
    )
    return _to_out(row)


@router.get("", response_model=MonthlyClosingListResponse)
async def list_closings(
    client_company_id: int | None = Query(default=None),
    year: int | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> MonthlyClosingListResponse:
    _ensure_staff(current_user)
    stmt = select(MonthlyClosing).where(MonthlyClosing.tenant_id == current_user.tenant_id)
    if client_company_id is not None:
        stmt = stmt.where(MonthlyClosing.client_company_id == client_company_id)
    if year is not None:
        stmt = stmt.where(MonthlyClosing.year == year)
    stmt = stmt.order_by(MonthlyClosing.year.desc(), MonthlyClosing.month.desc())
    rows = (await db.execute(stmt)).scalars().all()
    return MonthlyClosingListResponse(items=[_to_out(r) for r in rows], total=len(rows))


async def _get_owned(
    db: AsyncSession, current_user: CurrentUser, closing_id: int
) -> MonthlyClosing:
    row = (
        await db.execute(
            select(MonthlyClosing).where(
                MonthlyClosing.id == closing_id,
                MonthlyClosing.tenant_id == current_user.tenant_id,
            )
        )
    ).scalar_one_or_none()
    if row is None:
        raise ValidationError("월마감을 찾을 수 없습니다.")
    return row


@router.get("/{closing_id}", response_model=MonthlyClosingOut)
async def get_closing(
    closing_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> MonthlyClosingOut:
    _ensure_staff(current_user)
    return _to_out(await _get_owned(db, current_user, closing_id))


@router.patch("/{closing_id}/steps/{step_key}", response_model=MonthlyClosingOut)
async def update_step(
    closing_id: int,
    step_key: str,
    body: StepUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> MonthlyClosingOut:
    _ensure_staff(current_user)
    row = await _get_owned(db, current_user, closing_id)

    steps = _steps_from_db(row.steps)
    if all(s.key != step_key for s in steps):
        raise ValidationError(f"단계 '{step_key}'를 찾을 수 없습니다.")

    updated = set_step_done(steps, step_key, body.done, now_iso=datetime.utcnow().isoformat())
    row.steps = [s.model_dump() for s in updated]
    row.status = overall_status(updated)
    await db.commit()
    await db.refresh(row)
    logger.info(
        "monthly_closing.step_updated",
        tenant_id=current_user.tenant_id,
        closing_id=closing_id,
        step_key=step_key,
        done=body.done,
    )
    return _to_out(row)
