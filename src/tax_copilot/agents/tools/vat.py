"""결정론적 VAT 계산 도구.

LLM은 이 함수를 직접 호출한다. float 계산은 절대 금지 — 원 단위 정수와 Decimal만 사용.
tax_rate_basis_points=1000 은 10.00% (일반 부가세율).
"""

from decimal import ROUND_DOWN, Decimal


def calculate_vat_from_supply_value(
    supply_value_krw: int,
    tax_rate_basis_points: int = 1000,
) -> dict[str, int]:
    """공급가액에서 부가세와 합계금액을 계산한다.

    Args:
        supply_value_krw: 공급가액 (원 단위 정수).
        tax_rate_basis_points: 세율 (1000 = 10.00%, 기본 부가세율).

    Returns:
        supply_value_krw, vat_krw, total_krw, tax_rate_basis_points 를 담은 dict.

    Raises:
        ValueError: 음수 공급가액 또는 유효 범위 밖 세율.
    """
    if supply_value_krw < 0:
        raise ValueError(f"공급가액은 0 이상이어야 합니다: {supply_value_krw}")
    if not (0 <= tax_rate_basis_points <= 10000):
        raise ValueError(f"세율(basis points)은 0~10000 범위여야 합니다: {tax_rate_basis_points}")

    rate = Decimal(tax_rate_basis_points) / Decimal(10000)
    vat = (Decimal(supply_value_krw) * rate).quantize(Decimal("1"), rounding=ROUND_DOWN)

    return {
        "supply_value_krw": supply_value_krw,
        "vat_krw": int(vat),
        "total_krw": supply_value_krw + int(vat),
        "tax_rate_basis_points": tax_rate_basis_points,
    }


def calculate_entertainment_limit(
    total_expense_krw: int,
    revenue_krw: int,
) -> dict[str, int]:
    """접대비 손금 한도를 계산한다 (법인세법 제25조 기준).

    기본 한도: 1,200만원/년 + (수입금액 × 적용률)
    수입금액 100억 이하: 0.2%, 100억~500억: 0.1%, 500억 초과: 0.03%

    Args:
        total_expense_krw: 당기 접대비 지출 합계 (원).
        revenue_krw: 당기 수입금액 (원).

    Returns:
        limit_krw, excess_krw, deductible_krw 를 담은 dict.
    """
    BASE_LIMIT = 12_000_000  # 1,200만원

    # 수입금액 구간별 적용률 (basis points)
    rev = Decimal(revenue_krw)
    if revenue_krw <= 10_000_000_000:  # 100억 이하
        rate_bp = Decimal(20)  # 0.2%
    elif revenue_krw <= 50_000_000_000:  # 500억 이하
        rate_bp = Decimal(10)  # 0.1%
    else:
        rate_bp = Decimal(3)  # 0.03%

    rate_limit = (rev * rate_bp / Decimal(10000)).quantize(Decimal("1"), rounding=ROUND_DOWN)
    limit = BASE_LIMIT + int(rate_limit)
    deductible = min(total_expense_krw, limit)
    excess = max(0, total_expense_krw - limit)

    return {
        "limit_krw": limit,
        "deductible_krw": deductible,
        "excess_krw": excess,
    }
