"""거래처별 계정과목 규칙(반복 거래 학습) 순수 매칭 로직.

세무사가 "이 거래처는 항상 이 계정과목"이라고 한 번 정해주면, 다음부터 같은
거래처는 자동으로 그 계정과목으로 분류된다. 키워드 분류기(account_classifier)
보다 우선한다. core/ 레이어이므로 표준 라이브러리 + pydantic만 사용한다.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

from tax_copilot.core.tax.schemas import AccountCode

MatchType = Literal["exact", "contains"]


class MerchantRule(BaseModel):
    """가맹점명 → 계정과목 학습 규칙 한 건."""

    match_type: MatchType
    pattern: str
    account_code: AccountCode


def match_account_rule(
    merchant_name: str | None,
    rules: list[MerchantRule],
) -> tuple[AccountCode, str] | None:
    """학습된 규칙 중 가맹점명에 매칭되는 첫 규칙을 반환한다.

    'exact'(완전 일치)를 'contains'(부분 포함)보다 먼저 평가해, 더 구체적인
    규칙이 우선하도록 한다. 매칭 없으면 None.
    """
    if not merchant_name:
        return None

    name_lower = merchant_name.lower()

    for rule in rules:
        if rule.match_type == "exact" and rule.pattern.lower() == name_lower:
            return rule.account_code, f"학습 규칙(완전일치) '{rule.pattern}'"

    for rule in rules:
        if rule.match_type == "contains" and rule.pattern.lower() in name_lower:
            return rule.account_code, f"학습 규칙(포함) '{rule.pattern}'"

    return None
