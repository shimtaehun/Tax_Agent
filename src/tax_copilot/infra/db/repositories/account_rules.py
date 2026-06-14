"""계정과목 학습 규칙 조회 헬퍼.

worker(영수증 처리)와 API가 공통으로 사용한다. 테넌트 전역 규칙과 해당
고객사 전용 규칙을 함께 로드한다.
"""

from __future__ import annotations

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from tax_copilot.core.tax.account_rules import MerchantRule
from tax_copilot.core.tax.schemas import AccountCode
from tax_copilot.infra.db.models.account_rule import AccountRule


async def load_merchant_rules(
    db: AsyncSession,
    tenant_id: int,
    client_company_id: int | None,
) -> list[MerchantRule]:
    """테넌트 전역 + 해당 고객사 규칙을 순수 도메인 모델로 로드한다.

    고객사 전용 규칙(client_company_id 일치)을 전역 규칙보다 앞에 둬서 더
    구체적인 규칙이 먼저 평가되도록 한다.
    """
    result = await db.execute(
        select(AccountRule)
        .where(
            AccountRule.tenant_id == tenant_id,
            or_(
                AccountRule.client_company_id == client_company_id,
                AccountRule.client_company_id.is_(None),
            ),
        )
        .order_by(AccountRule.client_company_id.is_(None), AccountRule.id)
    )
    rows = result.scalars().all()
    return [
        MerchantRule(
            match_type="exact" if r.match_type == "exact" else "contains",
            pattern=r.pattern,
            account_code=_coerce_account_code(r.account_code),
        )
        for r in rows
    ]


def _coerce_account_code(value: str) -> AccountCode:
    """DB 문자열을 AccountCode literal로 좁힌다 (미등록 값은 미분류)."""
    from typing import get_args

    if value in get_args(AccountCode):
        return value  # type: ignore[return-value]
    return "미분류"
