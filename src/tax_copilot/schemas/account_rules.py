from datetime import datetime
from typing import Literal

from pydantic import BaseModel

from tax_copilot.core.tax.schemas import AccountCode


class AccountRuleCreate(BaseModel):
    pattern: str
    account_code: AccountCode
    match_type: Literal["exact", "contains"] = "contains"
    # None이면 테넌트 전역 규칙
    client_company_id: int | None = None


class LearnFromReceiptRequest(BaseModel):
    """기존 영수증의 가맹점→계정과목 분류를 규칙으로 학습한다."""

    receipt_id: int
    match_type: Literal["exact", "contains"] = "contains"
    # 규칙 범위. None이면 해당 영수증의 고객사 전용으로 생성.
    scope_tenant_wide: bool = False


class AccountRuleOut(BaseModel):
    id: int
    tenant_id: int
    client_company_id: int | None
    match_type: str
    pattern: str
    account_code: str
    hit_count: int
    created_at: datetime


class AccountRuleListResponse(BaseModel):
    items: list[AccountRuleOut]
    total: int
