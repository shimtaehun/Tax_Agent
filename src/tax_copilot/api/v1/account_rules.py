"""계정과목 학습 규칙(반복 거래 자동 분류) 관리 API.

세무사(staff/admin)가 거래처별 규칙을 만들고 관리한다. 한 번 학습하면 이후
같은 가맹점 거래는 키워드 분류기보다 우선해 자동 분류된다.
- GET    /account-rules
- POST   /account-rules
- POST   /account-rules/learn-from-receipt
- DELETE /account-rules/{rule_id}
"""

import structlog
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from tax_copilot.api.deps import CurrentUser, get_current_user, get_db
from tax_copilot.core.exceptions import AuthorizationError, ValidationError
from tax_copilot.infra.db.models.account_rule import AccountRule
from tax_copilot.infra.db.models.receipt import Receipt
from tax_copilot.infra.db.models.user import ROLE_CLIENT
from tax_copilot.schemas.account_rules import (
    AccountRuleCreate,
    AccountRuleListResponse,
    AccountRuleOut,
    LearnFromReceiptRequest,
)

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/account-rules", tags=["account-rules"])


def _ensure_staff(current_user: CurrentUser) -> None:
    if current_user.role == ROLE_CLIENT:
        raise AuthorizationError("고객사 계정은 계정과목 규칙을 관리할 수 없습니다.")


def _to_out(rule: AccountRule) -> AccountRuleOut:
    return AccountRuleOut(
        id=rule.id,
        tenant_id=rule.tenant_id,
        client_company_id=rule.client_company_id,
        match_type=rule.match_type,
        pattern=rule.pattern,
        account_code=rule.account_code,
        hit_count=rule.hit_count,
        created_at=rule.created_at,
    )


@router.get("", response_model=AccountRuleListResponse)
async def list_rules(
    client_company_id: int | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> AccountRuleListResponse:
    _ensure_staff(current_user)
    stmt = select(AccountRule).where(AccountRule.tenant_id == current_user.tenant_id)
    if client_company_id is not None:
        stmt = stmt.where(AccountRule.client_company_id == client_company_id)
    stmt = stmt.order_by(AccountRule.id.desc())
    rows = (await db.execute(stmt)).scalars().all()
    return AccountRuleListResponse(items=[_to_out(r) for r in rows], total=len(rows))


@router.post("", response_model=AccountRuleOut)
async def create_rule(
    body: AccountRuleCreate,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> AccountRuleOut:
    _ensure_staff(current_user)
    rule = AccountRule(
        tenant_id=current_user.tenant_id,
        client_company_id=body.client_company_id,
        created_by=current_user.user_id,
        match_type=body.match_type,
        pattern=body.pattern.strip(),
        account_code=body.account_code,
    )
    db.add(rule)
    await db.commit()
    await db.refresh(rule)
    logger.info(
        "account_rule.created",
        tenant_id=current_user.tenant_id,
        rule_id=rule.id,
        pattern=rule.pattern,
        account_code=rule.account_code,
    )
    return _to_out(rule)


@router.post("/learn-from-receipt", response_model=AccountRuleOut)
async def learn_from_receipt(
    body: LearnFromReceiptRequest,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> AccountRuleOut:
    """기존 영수증의 가맹점명·계정과목으로 규칙을 학습한다."""
    _ensure_staff(current_user)
    receipt = (
        await db.execute(
            select(Receipt).where(
                Receipt.id == body.receipt_id,
                Receipt.tenant_id == current_user.tenant_id,
            )
        )
    ).scalar_one_or_none()
    if receipt is None:
        raise ValidationError("영수증을 찾을 수 없습니다.")

    parsed = receipt.parsed_data or {}
    merchant = parsed.get("merchant_name") or (parsed.get("calculation_result") or {}).get(
        "merchant_name"
    )
    if not merchant:
        raise ValidationError("영수증에 가맹점명이 없어 규칙을 학습할 수 없습니다.")
    if not receipt.account_code:
        raise ValidationError("영수증에 계정과목이 없어 규칙을 학습할 수 없습니다.")

    rule = AccountRule(
        tenant_id=current_user.tenant_id,
        client_company_id=None if body.scope_tenant_wide else receipt.client_company_id,
        created_by=current_user.user_id,
        match_type=body.match_type,
        pattern=str(merchant).strip(),
        account_code=receipt.account_code,
    )
    db.add(rule)
    await db.commit()
    await db.refresh(rule)
    logger.info(
        "account_rule.learned",
        tenant_id=current_user.tenant_id,
        rule_id=rule.id,
        receipt_id=body.receipt_id,
        pattern=rule.pattern,
    )
    return _to_out(rule)


@router.delete("/{rule_id}")
async def delete_rule(
    rule_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> dict[str, str]:
    _ensure_staff(current_user)
    rule = (
        await db.execute(
            select(AccountRule).where(
                AccountRule.id == rule_id,
                AccountRule.tenant_id == current_user.tenant_id,
            )
        )
    ).scalar_one_or_none()
    if rule is None:
        raise ValidationError("규칙을 찾을 수 없습니다.")
    await db.delete(rule)
    await db.commit()
    return {"status": "deleted"}
