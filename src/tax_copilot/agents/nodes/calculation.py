"""세액 계산 노드.

결정론적 Python 함수로 계산한다. LLM이 숫자를 직접 계산하는 일은 없다.
"""

from tax_copilot.agents.state import AgentState
from tax_copilot.agents.tools.vat import calculate_vat_from_supply_value


async def calculation_node(state: AgentState) -> dict:
    """parsed_receipt의 공급가액으로 VAT를 검증 계산한다."""
    from decimal import ROUND_DOWN, Decimal

    parsed = state.get("parsed_receipt") or {}
    supply_value = parsed.get("supply_value_krw")

    # 공급가액 없으면 총액에서 역산 (카드/간이영수증 등 VAT 미분리 케이스)
    if supply_value is None:
        total = parsed.get("total_amount_krw")
        if total is None:
            return {"calculation_result": None}
        supply_value = int(
            (Decimal(total) / Decimal("1.1")).quantize(Decimal("1"), rounding=ROUND_DOWN)
        )

    result = calculate_vat_from_supply_value(supply_value_krw=int(supply_value))
    return {"calculation_result": result}
